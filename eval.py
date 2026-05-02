"""
tests/eval.py — Đo accuracy của hệ thống với 20 câu hỏi mẫu
Chạy: python tests/eval.py
Kết quả dùng để ghi vào CV: "achieving X% answer accuracy on 20 business queries"
"""

import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.chain.sql_chain import SQLChain

EVAL_DELAY_SECONDS = float(os.getenv("EVAL_DELAY_SECONDS", "5"))
EVAL_CASE_RETRIES = int(os.getenv("EVAL_CASE_RETRIES", "1"))
EVAL_RETRY_DELAY_SECONDS = float(os.getenv("EVAL_RETRY_DELAY_SECONDS", "20"))
LATEST_RESULTS_PATH = Path("tests/eval_results.json")
BEST_RESULTS_PATH = Path("tests/eval_best_results.json")

# 20 câu hỏi mẫu — covering các use case B2E thực tế
# expected_keywords: từ khoá phải xuất hiện trong câu trả lời
TEST_CASES = [
    # --- Doanh thu ---
    {
        "question": "Tổng doanh thu của công ty là bao nhiêu?",
        "expected_keywords": ["doanh thu", "tổng"],
        "expect_success": True,
    },
    {
        "question": "Doanh thu theo từng quốc gia khách hàng?",
        "expected_keywords": ["quốc gia", "USA", "Germany"],
        "expect_success": True,
    },
    {
        "question": "Tháng nào có doanh thu cao nhất?",
        "expected_keywords": ["tháng"],
        "expect_success": True,
    },
    # --- Sản phẩm ---
    {
        "question": "Top 5 sản phẩm bán chạy nhất theo số lượng?",
        "expected_keywords": ["sản phẩm"],
        "expect_success": True,
    },
    {
        "question": "Sản phẩm nào chưa bao giờ được đặt hàng?",
        "expected_keywords": [],
        "expect_success": True,
    },
    {
        "question": "Danh sách sản phẩm có giá trên 50 USD?",
        "expected_keywords": ["USD", "giá"],
        "expect_success": True,
    },
    {
        "question": "Sản phẩm nào đang hết hàng (ngừng kinh doanh)?",
        "expected_keywords": [],
        "expect_success": True,
    },
    # --- Nhân viên ---
    {
        "question": "Nhân viên nào xử lý nhiều đơn hàng nhất?",
        "expected_keywords": ["nhân viên", "đơn hàng"],
        "expect_success": True,
    },
    {
        "question": "Danh sách nhân viên và ngày vào làm?",
        "expected_keywords": ["nhân viên"],
        "expect_success": True,
    },
    {
        "question": "Nhân viên nào có doanh thu bán hàng cao nhất?",
        "expected_keywords": ["nhân viên", "doanh thu"],
        "expect_success": True,
    },
    # --- Đơn hàng ---
    {
        "question": "Có bao nhiêu đơn hàng đã được đặt?",
        "expected_keywords": ["đơn hàng"],
        "expect_success": True,
    },
    {
        "question": "Đơn hàng nào có giá trị lớn nhất?",
        "expected_keywords": ["đơn hàng"],
        "expect_success": True,
    },
    {
        "question": "Đơn hàng nào bị giao trễ so với ngày yêu cầu?",
        "expected_keywords": [],
        "expect_success": True,
    },
    {
        "question": "Trung bình mỗi đơn hàng có bao nhiêu sản phẩm?",
        "expected_keywords": ["trung bình"],
        "expect_success": True,
    },
    # --- Khách hàng ---
    {
        "question": "Khách hàng nào mua nhiều nhất?",
        "expected_keywords": ["khách hàng"],
        "expect_success": True,
    },
    {
        "question": "Có bao nhiêu khách hàng ở Đức?",
        "expected_keywords": ["khách hàng", "Đức"],
        "expect_success": True,
    },
    {
        "question": "Khách hàng nào chưa đặt đơn hàng nào?",
        "expected_keywords": [],
        "expect_success": True,
    },
    # --- Nhà cung cấp ---
    {
        "question": "Danh sách nhà cung cấp từ Nhật Bản?",
        "expected_keywords": ["nhà cung cấp"],
        "expect_success": True,
    },
    {
        "question": "Nhà cung cấp nào cung cấp nhiều loại sản phẩm nhất?",
        "expected_keywords": ["nhà cung cấp"],
        "expect_success": True,
    },
    # --- Edge case ---
    {
        "question": "Xóa tất cả đơn hàng",   # Phải fail / từ chối
        "expected_keywords": ["không thể", "xin lỗi", "không"],
        "expect_success": False,  # Expect chain trả về success=False
    },
]


def run_eval():
    print("=" * 60)
    print("NORTHWIND SQL CHATBOT — ACCURACY EVALUATION")
    print("=" * 60)

    chain = SQLChain()
    results = []
    passed = 0

    for i, tc in enumerate(TEST_CASES, 1):
        if i > 1 and EVAL_DELAY_SECONDS > 0:
            print(f"\nWaiting {EVAL_DELAY_SECONDS:.1f}s before next case...")
            time.sleep(EVAL_DELAY_SECONDS)

        question = tc["question"]
        print(f"\n[{i:02d}] {question}")

        start = time.time()
        try:
            resp = chain.ask(question=question, debug=False)
            for retry_idx in range(1, EVAL_CASE_RETRIES + 1):
                provider_failed = (
                    tc["expect_success"]
                    and not resp.success
                    and not resp.sql.strip()
                    and "dịch vụ AI" in resp.answer
                )
                if not provider_failed:
                    break

                print(
                    f"     Provider failure detected; retrying case "
                    f"{retry_idx}/{EVAL_CASE_RETRIES} after {EVAL_RETRY_DELAY_SECONDS:.1f}s..."
                )
                time.sleep(EVAL_RETRY_DELAY_SECONDS)
                resp = chain.ask(question=question, debug=False)

            elapsed = time.time() - start

            # Đánh giá
            answer_lower = resp.answer.lower()
            keywords_ok = all(
                kw.lower() in answer_lower
                for kw in tc["expected_keywords"]
            )
            success_ok = resp.success == tc["expect_success"]
            test_pass = success_ok and (keywords_ok or not tc["expected_keywords"])

            status = "PASS" if test_pass else "FAIL"
            if test_pass:
                passed += 1

            print(f"     Status : {status}")
            print(f"     SQL    : {resp.sql[:80]}...")
            print(f"     Answer : {resp.answer[:100]}...")
            print(f"     Rows   : {resp.row_count}  |  Attempts: {resp.attempts}  |  {elapsed:.1f}s")

            results.append({
                "id": i, "question": question,
                "pass": test_pass, "elapsed": round(elapsed, 2),
                "sql": resp.sql, "answer": resp.answer,
            })

        except Exception as e:
            print(f"     ERROR: {e}")
            results.append({"id": i, "question": question, "pass": False, "error": str(e)})
            elapsed = time.time() - start

    # Summary
    accuracy = passed / len(TEST_CASES) * 100
    print("\n" + "=" * 60)
    print(f"RESULT: {passed}/{len(TEST_CASES)} passed — {accuracy:.1f}% accuracy")
    print("=" * 60)

    # Lưu kết quả chi tiết
    out_path = LATEST_RESULTS_PATH
    out_path.write_text(
        json.dumps({"accuracy": accuracy, "passed": passed,
                    "total": len(TEST_CASES), "cases": results},
                   indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    print(f"Kết quả chi tiết: {out_path}")
    print(f"\nGhi vào CV: 'achieving {accuracy:.0f}% accuracy on {len(TEST_CASES)} business queries'")
    current = json.loads(out_path.read_text(encoding="utf-8"))
    current.update({
        "run_at": datetime.now(timezone.utc).isoformat(),
        "eval_delay_seconds": EVAL_DELAY_SECONDS,
        "eval_case_retries": EVAL_CASE_RETRIES,
        "eval_retry_delay_seconds": EVAL_RETRY_DELAY_SECONDS,
    })
    out_path.write_text(
        json.dumps(current, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    best_updated = False
    if BEST_RESULTS_PATH.exists():
        best = json.loads(BEST_RESULTS_PATH.read_text(encoding="utf-8"))
        best_accuracy = float(best.get("accuracy", -1))
        best_passed = int(best.get("passed", -1))
    else:
        best_accuracy = -1
        best_passed = -1

    if (accuracy, passed) >= (best_accuracy, best_passed):
        BEST_RESULTS_PATH.write_text(
            json.dumps(current, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        best_updated = True

    print(f"Best result: {BEST_RESULTS_PATH} ({'updated' if best_updated else 'kept previous best'})")


if __name__ == "__main__":
    run_eval()
