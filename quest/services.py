from .models import Quest
from accounts.models import User
from datetime import date
from characters.models import CharacterGrowthEvent, CharacterState

######### 상태 전이 및 기능 구현 #########

class InvalidTransition(Exception): pass
class QuestAlreadyChecked(Exception): pass

QUEST_DEADLINE_DAYS = 7  # started_at으로부터 이 일수가 지나면 D-day 만료(FAILED) 처리


def sync_active_quest_state(user: User, today: date) -> None:
    """
    유저의 ACTIVE 퀘스트가 D-day(시작일로부터 QUEST_DEADLINE_DAYS일)를 넘겼으면 FAILED로 정리한다.
    퀘스트는 한 번에 하나만 ACTIVE로 진행 가능해서, 이걸 안 하면 방치된 퀘스트가
    영원히 ACTIVE로 남아 새 퀘스트를 시작할 수 없게 막혀버린다.
    """
    active_quest = Quest.objects.filter(
        cycle__user=user, state=Quest.State.ACTIVE
    ).first()

    if active_quest is None:
        return

    days_since_start = (today - active_quest.started_at).days
    if days_since_start >= QUEST_DEADLINE_DAYS:
        active_quest.state = Quest.State.FAILED
        active_quest.save(update_fields=['state'])

def check_for_quest(quest: Quest, today: date) -> Quest:

    if quest.state == Quest.State.ACTIVE and (today - quest.started_at).days >= QUEST_DEADLINE_DAYS:
        quest.state = Quest.State.FAILED
        quest.save(update_fields=['state'])

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

    char_state = user.character_state
    char_state.total_score += score
    char_state.save(update_fields=['total_score'])

    CharacterGrowthEvent.objects.create(
        char_state = char_state,
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