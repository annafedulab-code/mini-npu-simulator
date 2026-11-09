"""
Mini NPU Simulator
- 필터(정답 도장)와 패턴(검사할 그림)을 겹쳐서
  같은 자리끼리 곱하고 모두 더하는 MAC 연산으로 모양을 판별한다.
- 외부 라이브러리 없이 파이썬 표준 라이브러리(json, time, os)만 사용한다.
"""

import json
import os
import time

# ------------------------------------------------------------
# [설정값] 프로그램 전체에서 쓰는 기준 숫자
# ------------------------------------------------------------
EPSILON = 1e-9        # 두 점수 차이가 이것보다 작으면 "동점"으로 본다
REPEAT_COUNT = 10     # 시간 측정 시 MAC 연산을 반복하는 횟수
DATA_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data.json")

LABEL_CROSS = "Cross"
LABEL_X = "X"
LABEL_UNDECIDED = "UNDECIDED"


# ============================================================
# 1. 데이터 구조: n x n 2차원 배열(표) 만들기 / 값 쓰기 / 값 읽기
# ============================================================
def create_matrix(n):
    """n x n 크기의, 0.0으로 채워진 표를 만든다."""
    return [[0.0 for _ in range(n)] for _ in range(n)]


def set_value(matrix, row, col, value):
    """표의 (row, col) 자리에 값을 저장한다."""
    matrix[row][col] = value


def get_value(matrix, row, col):
    """표의 (row, col) 자리에 있는 값을 읽어온다."""
    return matrix[row][col]


def get_square_size(matrix):
    """
    표가 정사각형(n x n)이면 n을 돌려주고,
    모양이 잘못되었으면 None을 돌려준다.
    """
    if not isinstance(matrix, list) or len(matrix) == 0:
        return None
    n = len(matrix)
    for row in matrix:
        if not isinstance(row, list) or len(row) != n:
            return None
        for value in row:
            # True/False도 숫자로 취급되므로 따로 막는다
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                return None
    return n


# ============================================================
# 2. 라벨 정규화: 여러 이름표를 표준 이름표(Cross / X)로 통일
# ============================================================
LABEL_MAP = {
    "+": LABEL_CROSS,
    "cross": LABEL_CROSS,
    "x": LABEL_X,
}


def normalize_label(raw_label):
    """'+', 'cross' -> Cross / 'x' -> X 로 바꾼다. 모르는 값이면 None."""
    if not isinstance(raw_label, str):
        return None
    return LABEL_MAP.get(raw_label.strip().lower())


# ============================================================
# 3. MAC 연산: 같은 자리끼리 곱하고(Multiply) 모두 더한다(Accumulate)
# ============================================================
def mac(pattern, filter_matrix):
    """패턴과 필터를 겹쳐 같은 위치의 숫자끼리 곱한 뒤 전부 더한 점수를 돌려준다."""
    n = len(pattern)
    total = 0.0
    for row in range(n):
        for col in range(n):
            total += get_value(pattern, row, col) * get_value(filter_matrix, row, col)
    return total


# ============================================================
# 4. 점수 비교 정책: 허용오차(epsilon) 기반
# ============================================================
def judge(score_a, score_b, label_a, label_b):
    """
    두 점수를 비교해 더 큰 쪽의 라벨을 돌려준다.
    차이가 EPSILON보다 작으면 동점으로 보고 UNDECIDED를 돌려준다.
    """
    if abs(score_a - score_b) < EPSILON:
        return LABEL_UNDECIDED
    return label_a if score_a > score_b else label_b


# ============================================================
# 5. 성능 측정: MAC 연산만 REPEAT_COUNT번 반복해서 평균 시간(ms)을 잰다
# ============================================================
def measure_mac_time(pattern, filter_matrix, repeat=REPEAT_COUNT):
    """입출력 시간은 빼고, MAC 함수 호출 구간만 측정한다."""
    start = time.perf_counter()
    for _ in range(repeat):
        mac(pattern, filter_matrix)
    end = time.perf_counter()
    return (end - start) * 1000 / repeat


# ============================================================
# 6. (보너스) 패턴 생성기: 크기 n을 넣으면 십자가/X 모양을 자동으로 만든다
# ============================================================
def make_cross(n):
    """가운데 가로줄과 세로줄이 1인 십자가 모양 표."""
    matrix = create_matrix(n)
    mid = n // 2
    for i in range(n):
        set_value(matrix, mid, i, 1.0)
        set_value(matrix, i, mid, 1.0)
    return matrix


def make_x(n):
    """두 대각선이 1인 X 모양 표."""
    matrix = create_matrix(n)
    for i in range(n):
        set_value(matrix, i, i, 1.0)
        set_value(matrix, i, n - 1 - i, 1.0)
    return matrix


def print_performance_table(sizes):
    """크기별 평균 연산 시간과 연산 횟수(N^2)를 표로 출력한다."""
    print(f"{'크기':<10}{'평균 시간(ms)':>16}{'연산 횟수(N^2)':>18}")
    print("-" * 46)
    for n in sizes:
        pattern = make_cross(n)
        filter_matrix = make_x(n)
        avg_ms = measure_mac_time(pattern, filter_matrix)
        size_text = f"{n}x{n}"
        print(f"{size_text:<10}{avg_ms:>16.4f}{n * n:>18}")


def print_section(title):
    print()
    print("#" + "-" * 45)
    print(f"# {title}")
    print("#" + "-" * 45)


# ============================================================
# 7. 모드 1: 사용자가 3x3 필터와 패턴을 직접 입력
# ============================================================
def read_matrix_from_console(name, n=3):
    """
    n줄을 입력받아 n x n 표를 만든다.
    한 줄에 숫자가 n개가 아니거나 숫자가 아닌 값이 있으면
    안내 문구를 보여주고 그 줄을 다시 입력받는다.
    """
    print(f"{name} ({n}줄 입력, 공백 구분)")
    matrix = create_matrix(n)
    row = 0
    while row < n:
        line = input().strip()
        parts = line.split()

        if len(parts) != n:
            print(f"입력 형식 오류: 각 줄에 {n}개의 숫자를 공백으로 구분해 입력하세요. "
                  f"({row + 1}번째 줄을 다시 입력하세요)")
            continue

        try:
            numbers = [float(p) for p in parts]
        except ValueError:
            print(f"입력 형식 오류: 숫자만 입력할 수 있습니다. "
                  f"({row + 1}번째 줄을 다시 입력하세요)")
            continue

        for col in range(n):
            set_value(matrix, row, col, numbers[col])
        row += 1
    return matrix


def print_matrix(matrix):
    for row in matrix:
        print("  " + " ".join(str(v) for v in row))


def run_user_input_mode():
    print_section("[1] 필터 입력")
    filter_a = read_matrix_from_console("필터 A")
    print()
    filter_b = read_matrix_from_console("필터 B")

    print("\n저장된 필터 A:")
    print_matrix(filter_a)
    print("저장된 필터 B:")
    print_matrix(filter_b)

    print_section("[2] 패턴 입력")
    pattern = read_matrix_from_console("패턴")

    print_section("[3] MAC 결과")
    score_a = mac(pattern, filter_a)
    score_b = mac(pattern, filter_b)
    avg_ms = (measure_mac_time(pattern, filter_a) + measure_mac_time(pattern, filter_b)) / 2
    result = judge(score_a, score_b, "A", "B")

    print(f"A 점수: {score_a}")
    print(f"B 점수: {score_b}")
    print(f"연산 시간(평균/{REPEAT_COUNT}회): {avg_ms:.4f} ms")
    if result == LABEL_UNDECIDED:
        print(f"판정: 판정 불가 (|A-B| < {EPSILON})")
    else:
        print(f"판정: {result}")

    print_section(f"[4] 성능 분석 (평균/{REPEAT_COUNT}회)")
    print_performance_table([3])


# ============================================================
# 8. 모드 2: data.json 분석
# ============================================================
def load_json(path):
    """data.json을 읽는다. 실패하면 None을 돌려주고 이유를 출력한다."""
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"오류: {path} 파일을 찾을 수 없습니다.")
    except json.JSONDecodeError as e:
        print(f"오류: data.json 형식이 올바르지 않습니다. ({e})")
    return None


def parse_size_from_key(key, prefix="size_"):
    """
    'size_13_2' 같은 키에서 크기 13을 꺼낸다.
    형식이 맞지 않으면 None.
    """
    if not isinstance(key, str) or not key.startswith(prefix):
        return None
    parts = key[len(prefix):].split("_")
    if not parts or not parts[0].isdigit():
        return None
    return int(parts[0])


def load_filters(data):
    """
    filters 부분을 읽어 {크기: {'Cross': 표, 'X': 표}} 모양으로 정리한다.
    필터 키('cross', 'x')는 표준 라벨로 정규화한다.
    """
    filters = {}
    raw_filters = data.get("filters")
    if not isinstance(raw_filters, dict):
        print("x filters 항목이 없거나 형식이 잘못되었습니다.")
        return filters

    for size_key, filter_group in raw_filters.items():
        n = parse_size_from_key(size_key)
        if n is None or not isinstance(filter_group, dict):
            print(f"x {size_key}: 키 형식 오류로 건너뜀")
            continue

        group = {}
        for raw_label, matrix in filter_group.items():
            label = normalize_label(raw_label)
            if label is None:
                print(f"x {size_key}.{raw_label}: 알 수 없는 라벨이라 건너뜀")
                continue
            if get_square_size(matrix) != n:
                print(f"x {size_key}.{raw_label}: {n}x{n} 크기가 아니라 건너뜀")
                continue
            group[label] = matrix

        filters[n] = group
        loaded = ", ".join(sorted(group)) if group else "없음"
        print(f"v {size_key:<8} 필터 로드 완료 ({loaded})")
    return filters


def analyze_pattern(key, item, filters):
    """
    패턴 1개를 분석한다.
    돌려주는 값: (통과 여부, 실패 사유)
    어떤 문제가 생겨도 프로그램을 멈추지 않고 FAIL로 처리한다.
    """
    print(f"--- {key} ---")

    # (1) 키에서 크기 N 꺼내기
    n = parse_size_from_key(key)
    if n is None:
        reason = "키 형식 오류 (size_N_번호 형식이 아님)"
        print(f"FAIL ({reason})")
        return False, reason

    # (2) 패턴 데이터 확인
    if not isinstance(item, dict) or "input" not in item or "expected" not in item:
        reason = "스키마 오류 (input 또는 expected 없음)"
        print(f"FAIL ({reason})")
        return False, reason

    # (3) 해당 크기의 필터 찾기
    group = filters.get(n, {})
    if LABEL_CROSS not in group or LABEL_X not in group:
        reason = f"size_{n} 필터(Cross/X)를 찾을 수 없음"
        print(f"FAIL ({reason})")
        return False, reason

    # (4) 필터와 패턴 크기가 같은지 확인
    pattern = item["input"]
    pattern_size = get_square_size(pattern)
    if pattern_size != n:
        reason = f"크기 불일치 (필터 {n}x{n}, 패턴 {pattern_size}x{pattern_size})" \
            if pattern_size else f"패턴 모양 오류 ({n}x{n} 숫자 표가 아님)"
        print(f"FAIL ({reason})")
        return False, reason

    # (5) expected 라벨 정규화
    expected = normalize_label(item["expected"])
    if expected is None:
        reason = f"알 수 없는 expected 라벨: {item['expected']!r}"
        print(f"FAIL ({reason})")
        return False, reason

    # (6) MAC 연산 및 판정
    cross_score = mac(pattern, group[LABEL_CROSS])
    x_score = mac(pattern, group[LABEL_X])
    result = judge(cross_score, x_score, LABEL_CROSS, LABEL_X)

    print(f"Cross 점수: {cross_score}")
    print(f"X 점수: {x_score}")

    if result == expected:
        print(f"판정: {result} | expected: {expected} | PASS")
        return True, None

    if result == LABEL_UNDECIDED:
        reason = f"동점(UNDECIDED) 처리 규칙에 따라 FAIL (|Cross-X| < {EPSILON})"
        print(f"판정: {result} | expected: {expected} | FAIL (동점 규칙)")
    else:
        reason = f"판정 {result}가 expected {expected}와 다름"
        print(f"판정: {result} | expected: {expected} | FAIL")
    return False, reason


def run_json_mode():
    data = load_json(DATA_FILE)
    if data is None:
        return
    if not isinstance(data, dict):
        print("오류: data.json의 최상위 구조가 객체({})가 아닙니다.")
        return

    print_section("[1] 필터 로드")
    filters = load_filters(data)

    print_section("[2] 패턴 분석 (라벨 정규화 적용)")
    patterns = data.get("patterns")
    if not isinstance(patterns, dict):
        print("patterns 항목이 없거나 형식이 잘못되었습니다.")
        patterns = {}

    total = 0
    passed = 0
    failures = []
    for key, item in patterns.items():
        total += 1
        ok, reason = analyze_pattern(key, item, filters)
        if ok:
            passed += 1
        else:
            failures.append((key, reason))

    print_section(f"[3] 성능 분석 (평균/{REPEAT_COUNT}회)")
    sizes = [3] + sorted(n for n in filters if n != 3)
    print_performance_table(sizes)

    print_section("[4] 결과 요약")
    print(f"총 테스트: {total}개")
    print(f"통과: {passed}개")
    print(f"실패: {len(failures)}개")
    if failures:
        print("\n실패 케이스:")
        for key, reason in failures:
            print(f"- {key}: {reason}")
    print("\n(상세 원인 분석 및 복잡도 설명은 README.md의 \"결과 리포트\" 섹션 참고)")


# ============================================================
# 9. 프로그램 시작: 모드 선택
# ============================================================
def main():
    print("=== Mini NPU Simulator ===")
    print()
    print("[모드 선택]")
    print("1. 사용자 입력 (3x3)")
    print("2. data.json 분석")

    while True:
        choice = input("선택: ").strip()
        if choice == "1":
            run_user_input_mode()
            break
        if choice == "2":
            run_json_mode()
            break
        print("1 또는 2를 입력하세요.")


if __name__ == "__main__":
    try:
        main()
    except (KeyboardInterrupt, EOFError):
        print("\n프로그램을 종료합니다.")
