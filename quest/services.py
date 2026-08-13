from .models import User, Quest
from datetime import date

######### 상태 전이 및 기능 구현 #########

class InvalidTransition(Exception): pass
class QuestAlreadyChecked(Exception): pass

def check_for_quest(quest: Quest, today: date) -> Quest:

    if quest.state != Quest.State.ACTIVE:
        raise InvalidTransition("ACTIVE 상태의 퀘스트만 체크할 수 있습니다.")

    if quest.last_checked == today:
        raise QuestAlreadyChecked("오늘 이미 체크한 퀘스트입니다.")

    quest.last_checked = today

    if quest.count < 2:
        quest.count += 1
        quest.state = Quest.State.ACTIVE
    elif quest.count == 2:
        quest.count += 1
        quest.state = Quest.State.DONE        

    quest.save()

    return quest
        