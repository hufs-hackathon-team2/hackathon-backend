# 에셋 매칭용 시딩 마이그레이션.
# logs/constants.py의 ASSET_LIST(AI 프롬프트용 에셋 이름 목록)가 실제 Asset 테이블에는
# 한 번도 채워진 적이 없어서, 모든 플러스 로그의 에셋 매칭이 항상 DoesNotExist로 실패하고
# state=FAILED, asset=None으로 남던 문제를 고친다.
#
# category는 현재 어떤 로직에서도 필터링/조회에 쓰이지 않는(단순 필수 컬럼) 필드라
# action 텍스트 기반 키워드로 대략 분류했다. 실제 분류 기준이 필요해지면 그때 다시 정리할 것.
from django.db import migrations

from logs.constants import ASSET_LIST

CATEGORY_KEYWORDS = [
    ("exercise", [
        "달리기", "조깅", "걷기", "산책", "근력", "웨이트", "헬스", "요가", "명상", "스트레칭",
        "수영", "자전거", "등산", "클라이밍", "댄스", "축구", "농구", "테니스", "배드민턴", "야구",
        "스케이트", "태권도", "무술", "발레", "필라테스", "운동", "트레킹", "스키", "스노보드",
        "탁구", "배구", "연날리기",
    ]),
    ("drink", ["물 마시기", "수분", "우유", "차,", "커피", "물병", "텀블러", "꿀"]),
    ("food", [
        "샐러드", "채소", "브로콜리", "당근", "토마토", "오이", "잎채소", "아보카도", "옥수수",
        "감자", "고구마", "버섯", "파프리카", "피망", "양파", "마늘", "생강", "사과", "바나나",
        "포도", "딸기", "블루베리", "귤", "오렌지", "키위", "복숭아", "수박", "레몬", "올리브",
        "허브", "나물", "밥", "국", "탕", "죽", "시리얼", "오트밀", "생선", "계란", "고기",
        "빵", "치즈", "유제품", "견과류", "콩", "샌드위치", "도시락", "식사", "끼니", "초밥",
        "회", "주먹밥", "김밥", "만두", "면 요리", "파스타", "새우", "게,", "버터", "소금",
        "요리하기", "집밥", "찌개", "장보기", "케이크", "아이스크림", "쿠키", "초콜릿", "도넛",
        "사탕", "파이", "빙수", "푸딩",
    ]),
    ("rest", ["수면", "잠자기", "야간", "목욕", "반신욕", "샤워", "온천", "사우나", "이완", "휴식", "쉬기"]),
    ("routine", [
        "아침 기상", "일출", "기상", "알람", "손 씻기", "위생", "양치", "치아", "청소", "환경 정리",
        "피부", "보습", "금연",
    ]),
    ("health", [
        "심장", "심혈관", "폐", "호흡", "뇌", "정신 건강", "집중", "뼈", "관절", "영양제", "약",
        "예방접종", "검진", "진료", "회복", "부상", "병원", "시력", "눈", "청력", "귀", "코",
        "안경", "체중",
    ]),
    ("nature", [
        "햇빛", "맑은 날", "새싹", "성장", "식물", "나무", "공원", "산,", "바다", "파도", "꽃",
        "해바라기", "행운", "바람", "날씨", "캠핑", "눈,", "겨울", "눈사람", "비 오는", "환기",
    ]),
    ("achievement", [
        "칭찬", "반짝", "연속 기록", "열정", "목표", "완주", "완료", "체크", "기록하기", "일지",
        "노트", "일정", "꾸준함", "향상", "보상", "선물", "축하", "시간 재기", "타이머",
    ]),
    ("character", ["스티커", "고양이", "강아지", "토끼", "거북이", "새", "나비", "꿀벌", "마음"]),
    ("mindful", ["기도", "감사", "음악", "독서", "책", "대화", "상담", "생각 정리", "포옹", "위로", "관계", "만남", "약속", "아로마", "편지"]),
    ("accessibility", ["휠체어", "지팡이", "목발", "보청기"]),
    ("family", ["임신", "육아", "수유", "화장실"]),
    ("hobby", ["사진", "영화", "그림", "게임", "여행", "짐 싸기", "지도", "모임", "소풍", "함께 마시기", "디지털 디톡스"]),
    ("emotion", ["기분 좋음", "편안함", "안도", "스트레스 해소", "자신감", "뿌듯함", "고마움", "애정"]),
    ("transport", ["버스", "기차", "지하철", "학교", "회사", "편의점"]),
]


def categorize(action: str) -> str:
    for category, keywords in CATEGORY_KEYWORDS:
        if any(keyword in action for keyword in keywords):
            return category
    return "etc"


def seed_assets(apps, schema_editor):
    Asset = apps.get_model("logs", "Asset")
    for entry in ASSET_LIST:
        Asset.objects.get_or_create(
            asset_name=entry["asset_name"],
            defaults={
                "category": categorize(entry["action"]),
                "is_active": True,
            },
        )


def unseed_assets(apps, schema_editor):
    Asset = apps.get_model("logs", "Asset")
    asset_names = [entry["asset_name"] for entry in ASSET_LIST]
    Asset.objects.filter(asset_name__in=asset_names).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("logs", "0003_alter_pluslog_cycle_alter_pluslog_user"),
    ]

    operations = [
        migrations.RunPython(seed_assets, unseed_assets),
    ]
