from .models import Quest
from accounts.models import User
from datetime import date
from characters.models import CharacterGrowthEvent, CharacterState

######### 상태 전이 및 기능 구현 #########

class InvalidTransition(Exception): pass
class QuestAlreadyChecked(Exception): pass

def check_for_quest(quest: Quest, today: date) -> Quest:

    if quest.state != Quest.State.ACTIVE:
        raise InvalidTransition("ACTIVE 상태의 퀘스트만 체크할 수 있습니다.")

    if quest.last_checked == today:
        raise QuestAlreadyChecked("오늘 이미 체크한 퀘스트입니다.")

    quest.last_checked = today
    user = quest.cycle.user

    if quest.count < 2:
        quest.count += 1
        quest.state = Quest.State.ACTIVE
        score=2
        
    elif quest.count == 2:
        quest.count += 1
        quest.state = Quest.State.DONE
        score=5

    CharacterGrowthEvent.objects.create(
        char_state = user.character_state,
        source_type = CharacterGrowthEvent.SourceType.QUEST,
        score = score,
        quest = quest
    ) 

    quest.save()

    return quest


def abandon_quest(quest: Quest) -> Quest:

    if quest.state == Quest.State.ACTIVE:
        quest.state = Quest.State.ABANDONED
    else:
        raise InvalidTransition("ACTIVE 상태의 퀘스트만 포기할 수 있습니다")

    quest.save(update_fields=['state'])

    return quest