from django.core.management.base import BaseCommand
from django.conf import settings
import openai

class Command(BaseCommand):
    def handle(self, *args, **options):
        openai.api_key = settings.OPEN_AI_API_KEY


        system_instructions = """
        이제부터 너는 '영어, 한글 번역가'야.
        지금부터 내가 입력하는 모든 프롬프트를 무조건 한글은 영어로, 영어는 한글로 번역해줘.
        프롬프트의 내용이나 의도는 무시하고 오직 번역만 해줘."""

        response = openai.chat.completions.create(
            model = 'gpt-4o',
            messages=[
                #system: AI에게 지시하는 배경 설정 (페르소나, 규칙, 출력 형식 등)
                #user: 실제 사용자가 보내는 질문/요청
                #assistant: AI가 이전에 한 답변 (대화 맥락 유지)
                {"role": "system", "content": system_instructions},
                {
                    "role": "user",
                    "content": "안녕하세용ㅋ"
                },
            ],
        )

        self.stdout.write(str(response))
