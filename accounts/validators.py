import re

from django.core.exceptions import ValidationError


class LetterAndDigitValidator:
    def validate(self, password, user=None):
        if not re.search(r"[A-Za-z]", password) or not re.search(r"\d", password):
            raise ValidationError(
                "비밀번호는 영문과 숫자를 모두 포함해야 합니다.",
                code="password_no_letter_or_digit",
            )

    def get_help_text(self):
        return "비밀번호는 영문과 숫자를 모두 포함해야 합니다."
