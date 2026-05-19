#!/usr/bin/env python3
"""Submit a PDF to paperreview.ai and save the resulting review.

This script mirrors the public web frontend flow:
1. request a presigned S3 upload URL,
2. upload the local PDF to that URL,
3. confirm the upload to obtain a review token,
4. poll the review endpoint until the report is ready,
5. save both JSON and Markdown copies locally.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import requests


BASE_URL = "https://paperreview.ai"
SKILL_ROOT = Path(__file__).resolve().parents[1]
MAX_PDF_SIZE_BYTES = 10 * 1024 * 1024
DEFAULT_INITIAL_POLL_INTERVAL_SECONDS = 3 * 60
DEFAULT_POLL_INTERVAL_INCREMENT_SECONDS = 60
DEFAULT_MAX_WAIT_SECONDS = 24 * 60 * 60
DEFAULT_VENUE = "ICLR"
DEFAULT_OUTPUT_DIR_NAME = "paperreview_reviews"


class PaperReviewError(RuntimeError):
    """Raised for paperreview.ai API failures."""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Submit a PDF to paperreview.ai and save review JSON/Markdown.",
    )
    parser.add_argument(
        "pdf",
        type=Path,
        nargs="?",
        help="Path to the local PDF file. Omit when using --token to fetch an existing review.",
    )
    parser.add_argument(
        "--email",
        default=os.environ.get("PAPERREVIEW_EMAIL"),
        help="Email address for notification. Defaults to PAPERREVIEW_EMAIL when set.",
    )
    parser.add_argument(
        "--venue",
        default=DEFAULT_VENUE,
        help=f"Optional target venue, e.g. NeurIPS, ICML, ICLR. Default: {DEFAULT_VENUE}.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        help=(
            "Base directory where round folders, tokens, JSON, and Markdown files are saved. "
            f"Default: {DEFAULT_OUTPUT_DIR_NAME} next to the PDF, or under the current working "
            "directory in token mode; if run from the installed skill folder, token output "
            "defaults under the user home directory."
        ),
    )
    parser.add_argument(
        "--poll-interval",
        type=int,
        default=DEFAULT_INITIAL_POLL_INTERVAL_SECONDS,
        help=(
            "Seconds to wait before the first retry after a not-ready review response. "
            f"Default: {DEFAULT_INITIAL_POLL_INTERVAL_SECONDS}."
        ),
    )
    parser.add_argument(
        "--poll-increment",
        type=int,
        default=DEFAULT_POLL_INTERVAL_INCREMENT_SECONDS,
        help=(
            "Seconds to add to the polling interval after each not-ready response. "
            f"Default: {DEFAULT_POLL_INTERVAL_INCREMENT_SECONDS}."
        ),
    )
    parser.add_argument(
        "--max-wait",
        type=int,
        default=DEFAULT_MAX_WAIT_SECONDS,
        help=f"Maximum seconds to wait for the review. Default: {DEFAULT_MAX_WAIT_SECONDS}.",
    )
    parser.add_argument(
        "--no-wait",
        action="store_true",
        help="Submit and save the token only; do not poll for the finished review.",
    )
    parser.add_argument(
        "--confirm-external-upload",
        action="store_true",
        help="Required for PDF uploads; confirms the paper may be uploaded to paperreview.ai.",
    )
    parser.add_argument(
        "--base-url",
        default=BASE_URL,
        help=f"paperreview.ai base URL. Default: {BASE_URL}.",
    )
    parser.add_argument(
        "--token",
        help="Existing review token. If set, skip upload and only poll/fetch the review.",
    )
    parser.add_argument(
        "--output-prefix",
        help="Optional filename prefix for saved files. Default derives from PDF name or token mode.",
    )
    return parser.parse_args()


def require_pdf(path: Path) -> Path:
    pdf = path.expanduser().resolve()
    if not pdf.exists():
        raise PaperReviewError(f"PDF does not exist: {pdf}")
    if not pdf.is_file():
        raise PaperReviewError(f"PDF path is not a file: {pdf}")
    if pdf.suffix.lower() != ".pdf":
        raise PaperReviewError(f"Input must be a .pdf file: {pdf}")
    size = pdf.stat().st_size
    if size > MAX_PDF_SIZE_BYTES:
        mb = size / (1024 * 1024)
        raise PaperReviewError(f"PDF exceeds paperreview.ai 10MB limit: {mb:.2f}MB")
    return pdf


def default_output_base(pdf: Path | None) -> Path:
    if pdf is not None:
        candidate = pdf.parent / DEFAULT_OUTPUT_DIR_NAME
        try:
            candidate.resolve().relative_to(SKILL_ROOT)
        except ValueError:
            return candidate
        return Path.home() / DEFAULT_OUTPUT_DIR_NAME

    cwd = Path.cwd().resolve()
    try:
        cwd.relative_to(SKILL_ROOT)
    except ValueError:
        return cwd / DEFAULT_OUTPUT_DIR_NAME
    return Path.home() / DEFAULT_OUTPUT_DIR_NAME


def resolve_output_base(output_dir: Path | None, pdf: Path | None) -> Path:
    if output_dir is not None:
        return output_dir.expanduser().resolve()
    return default_output_base(pdf).resolve()


def request_upload_url(session: requests.Session, base_url: str, filename: str, venue: str) -> dict[str, Any]:
    response = session.post(
        f"{base_url}/api/get-upload-url",
        json={"filename": filename, "venue": venue or ""},
        timeout=60,
    )
    data = parse_json_response(response)
    if response.status_code == 429:
        raise PaperReviewError(data.get("detail", "Rate limit exceeded while requesting upload URL."))
    if not response.ok:
        raise PaperReviewError(data.get("detail", f"Failed to get upload URL: HTTP {response.status_code}"))
    required = ("success", "presigned_url", "presigned_fields", "s3_key")
    missing = [key for key in required if key not in data]
    if missing or not data.get("success"):
        raise PaperReviewError(f"Invalid upload URL response; missing {missing}")
    return data


def upload_to_s3(session: requests.Session, upload_data: dict[str, Any], pdf: Path) -> None:
    fields = upload_data["presigned_fields"]
    if not isinstance(fields, dict):
        raise PaperReviewError("Invalid presigned_fields in upload URL response.")

    with pdf.open("rb") as handle:
        files = {"file": (pdf.name, handle, "application/pdf")}
        response = session.post(upload_data["presigned_url"], data=fields, files=files, timeout=300)
    if not response.ok:
        raise PaperReviewError(f"S3 upload failed: HTTP {response.status_code} {response.reason}")


def confirm_upload(
    session: requests.Session,
    base_url: str,
    s3_key: str,
    venue: str,
    email: str,
) -> dict[str, Any]:
    response = session.post(
        f"{base_url}/api/confirm-upload",
        data={"s3_key": s3_key, "venue": venue or "", "email": email},
        timeout=60,
    )
    data = parse_json_response(response)
    if response.status_code == 429:
        raise PaperReviewError(data.get("detail", "Rate limit exceeded while confirming upload."))
    if not response.ok:
        raise PaperReviewError(data.get("detail", f"Failed to confirm upload: HTTP {response.status_code}"))
    if not data.get("success") or not data.get("token"):
        raise PaperReviewError("Upload confirmed but no review token was returned.")
    return data


def fetch_review(session: requests.Session, base_url: str, token: str) -> tuple[str, dict[str, Any] | None]:
    response = session.get(f"{base_url}/api/review/{token}", timeout=60)
    data = parse_json_response(response)
    if response.status_code == 202:
        detail = data.get("detail", "Review is still processing.")
        return detail, None
    if response.status_code == 429:
        raise PaperReviewError(data.get("detail", "Rate limit exceeded while polling review."))
    if not response.ok:
        raise PaperReviewError(data.get("detail", f"Failed to fetch review: HTTP {response.status_code}"))
    return "ready", data


def parse_json_response(response: requests.Response) -> dict[str, Any]:
    try:
        data = response.json()
    except ValueError as exc:
        preview = response.text[:500]
        raise PaperReviewError(f"Expected JSON response, got: {preview}") from exc
    if not isinstance(data, dict):
        raise PaperReviewError(f"Expected JSON object response, got {type(data).__name__}.")
    return data


def wait_for_review(
    session: requests.Session,
    base_url: str,
    token: str,
    poll_interval: int,
    poll_increment: int,
    max_wait: int,
) -> dict[str, Any]:
    if poll_interval < 30:
        raise PaperReviewError("--poll-interval should be at least 30 seconds to avoid excessive polling.")
    if poll_increment < 0:
        raise PaperReviewError("--poll-increment cannot be negative.")
    deadline = time.monotonic() + max_wait
    attempt = 1
    while True:
        try:
            status, review = fetch_review(session, base_url, token)
        except requests.RequestException as exc:
            status = f"transient network error: {exc}"
            review = None
        if review is not None:
            return review
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise PaperReviewError(f"Timed out waiting for review. Last status: {status}")
        current_interval = poll_interval + ((attempt - 1) * poll_increment)
        sleep_for = min(current_interval, int(remaining))
        print(f"[{timestamp()}] Review not ready yet ({status}); polling again in {sleep_for}s.")
        time.sleep(sleep_for)
        attempt += 1


def save_review(review: dict[str, Any], output_dir: Path, prefix: str) -> tuple[Path, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / f"{prefix}.json"
    md_path = output_dir / f"{prefix}.md"
    json_path.write_text(json.dumps(review, indent=2, ensure_ascii=False), encoding="utf-8")
    md_path.write_text(render_markdown(review), encoding="utf-8")
    return json_path, md_path


def save_token(
    token: str,
    output_dir: Path,
    prefix: str,
    *,
    base_url: str,
    venue: str,
    pdf: Path,
) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    token_path = output_dir / f"{prefix}_token.json"
    payload = {
        "token": token,
        "review_url": f"{base_url}/review/{token}",
        "api_url": f"{base_url}/api/review/{token}",
        "venue": venue,
        "pdf": str(pdf),
        "saved_at": timestamp(),
    }
    token_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    return token_path


def next_review_round_dir(reviews_dir: Path) -> Path:
    round_numbers: list[int] = []
    if reviews_dir.exists():
        for child in reviews_dir.iterdir():
            if not child.is_dir():
                continue
            match = re.fullmatch(r"round_(\d+)", child.name)
            if match:
                round_number = int(match.group(1))
                round_numbers.append(round_number)
                if not any(child.iterdir()):
                    return child
    next_round = max(round_numbers, default=0) + 1
    return reviews_dir / f"round_{next_round}"


def render_markdown(data: dict[str, Any]) -> str:
    lines: list[str] = []
    title = str(data.get("title") or "Paper Review")
    lines.extend([f"# {title}", ""])

    for label, key in (
        ("Venue", "venue"),
        ("Submitted", "submission_date"),
        ("Review date", "review_date"),
    ):
        value = data.get(key)
        if value:
            lines.extend([f"**{label}:** {value}", ""])

    if data.get("numerical_score") is not None:
        lines.extend([f"**Estimated Score:** {data['numerical_score']}/10", ""])

    sections = data.get("sections") or {}
    if not isinstance(sections, dict):
        sections = {}

    section_order = [
        ("summary", "Summary"),
        ("strengths", "Strengths"),
        ("weaknesses", "Weaknesses"),
        ("detailed_comments", "Detailed Comments"),
        ("questions", "Questions for Authors"),
        ("assessment", "Overall Assessment"),
        ("full_review", "Full Review"),
    ]
    for key, heading in section_order:
        content = sections.get(key)
        if isinstance(content, str) and content.strip():
            lines.extend([f"## {heading}", "", content.strip(), ""])

    binary_scores = sections.get("binary_scores")
    if binary_scores:
        lines.extend(["## Binary Scores", ""])
        lines.extend(render_value_as_markdown_list(binary_scores))
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def render_value_as_markdown_list(value: Any, indent: int = 0) -> list[str]:
    prefix = "  " * indent
    lines: list[str] = []
    if isinstance(value, dict):
        for key, item in value.items():
            if isinstance(item, (dict, list)):
                lines.append(f"{prefix}- **{key}:**")
                lines.extend(render_value_as_markdown_list(item, indent + 1))
            else:
                lines.append(f"{prefix}- **{key}:** {item}")
    elif isinstance(value, list):
        for item in value:
            if isinstance(item, (dict, list)):
                lines.append(f"{prefix}-")
                lines.extend(render_value_as_markdown_list(item, indent + 1))
            else:
                lines.append(f"{prefix}- {item}")
    else:
        lines.append(f"{prefix}- {value}")
    return lines


def safe_prefix(pdf: Path) -> str:
    stem = re.sub(r"[^A-Za-z0-9._-]+", "_", pdf.stem).strip("._-")
    if not stem:
        stem = "paper"
    return f"{stem}_paperreview"


def timestamp() -> str:
    return datetime.now(timezone.utc).astimezone().strftime("%Y-%m-%d %H:%M:%S %Z")


def main() -> int:
    args = parse_args()
    try:
        base_url = args.base_url.rstrip("/")
        session = requests.Session()
        # Avoid ambient OS proxy discovery; the local proxy has caused polling drops in this workspace.
        session.trust_env = False

        if args.token:
            if args.pdf:
                raise PaperReviewError("Do not pass a PDF path when using --token.")
            if args.no_wait:
                raise PaperReviewError("--no-wait cannot be used with --token.")
            reviews_dir = resolve_output_base(args.output_dir, None)
            output_dir = next_review_round_dir(reviews_dir)
            prefix = args.output_prefix or "paperreview_report"
            print(f"[{timestamp()}] Fetching existing review by token.")
            review = wait_for_review(
                session,
                base_url,
                args.token,
                args.poll_interval,
                args.poll_increment,
                args.max_wait,
            )
            json_path, md_path = save_review(review, output_dir, prefix)
            print(f"[{timestamp()}] Review saved:")
            print(f"  JSON: {json_path}")
            print(f"  Markdown: {md_path}")
            return 0

        if not args.pdf:
            raise PaperReviewError("PDF path is required unless --token is provided.")
        if not args.email:
            raise PaperReviewError("--email is required when uploading a PDF, or set PAPERREVIEW_EMAIL.")
        if not args.confirm_external_upload:
            raise PaperReviewError(
                "Refusing to upload without --confirm-external-upload. "
                "This confirms the PDF may be sent to paperreview.ai."
            )

        pdf = require_pdf(args.pdf)
        reviews_dir = resolve_output_base(args.output_dir, pdf)
        output_dir = next_review_round_dir(reviews_dir)
        prefix = args.output_prefix or safe_prefix(pdf)

        print(f"[{timestamp()}] Requesting upload URL...")
        upload_data = request_upload_url(session, base_url, pdf.name, args.venue)

        print(f"[{timestamp()}] Uploading PDF to presigned storage...")
        upload_to_s3(session, upload_data, pdf)

        print(f"[{timestamp()}] Confirming submission...")
        confirmation = confirm_upload(session, base_url, upload_data["s3_key"], args.venue, args.email)
        token = confirmation["token"]
        print(f"[{timestamp()}] Submission successful. Token: {token}")
        token_path = save_token(token, output_dir, prefix, base_url=base_url, venue=args.venue, pdf=pdf)
        print(f"[{timestamp()}] Token saved: {token_path}")

        if args.no_wait:
            print(f"[{timestamp()}] --no-wait set; exiting before polling.")
            return 0

        print(
            f"[{timestamp()}] Waiting for review. First retry in {args.poll_interval}s; "
            f"adding {args.poll_increment}s after each retry."
        )
        review = wait_for_review(
            session,
            base_url,
            token,
            args.poll_interval,
            args.poll_increment,
            args.max_wait,
        )
        json_path, md_path = save_review(review, output_dir, prefix)
        print(f"[{timestamp()}] Review saved:")
        print(f"  JSON: {json_path}")
        print(f"  Markdown: {md_path}")
        return 0
    except KeyboardInterrupt:
        print("\nInterrupted.", file=sys.stderr)
        return 130
    except PaperReviewError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    except requests.RequestException as exc:
        print(f"Network error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
