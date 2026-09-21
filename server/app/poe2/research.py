"""POE2 Chat admission policy; persisted by the shared research lifecycle."""
SOFT_CANDIDATES = 30
MAX_CANDIDATES = 60
MAX_ATTEMPTS = 120
MAX_TURN_ATTEMPTS = 12


def status(data, work):
    used = len(data.get('candidates', []))
    attempts = data.get('attempts', 0)
    turn = work.get('poe2Attempts', 0)
    return {'candidatesUsed': used, 'candidateLimit': MAX_CANDIDATES,
            'attemptsUsed': attempts, 'attemptLimit': MAX_ATTEMPTS,
            'turnAttemptsUsed': turn, 'turnAttemptLimit': MAX_TURN_ATTEMPTS,
            'candidatesRemaining': max(0, MAX_CANDIDATES-used),
            'turnAttemptsRemaining': max(0, MAX_TURN_ATTEMPTS-turn),
            'advice': '已有较多方案，请优先收敛；仍可继续必要对比。' if used >= SOFT_CANDIDATES else ''}


def reserve(data, work, key):
    """Called only for new execution, after reusable jobs have been checked."""
    candidates = data.get('candidates', [])
    code = None
    if work.get('poe2Attempts', 0) >= MAX_TURN_ATTEMPTS:
        code = 'POE2_RESEARCH_TURN_LIMIT'
    elif data.get('attempts', 0) >= MAX_ATTEMPTS or (key not in candidates and len(candidates) >= MAX_CANDIDATES):
        code = 'POE2_RESEARCH_SCOPE_LIMIT'
    if code:
        return {'status': 'blocked', 'errorCode': code, 'researchBudget': status(data, work),
                'nextAction': '本轮计算已达到保护上限，先总结已有结果；正常追问可继续。' if code.endswith('TURN_LIMIT') else
                '本研究新增计算已达上限，仍可读取、解释和对比已有结果；不要拆分同一研究绕过预算。'}
    if key not in candidates:
        data.setdefault('candidates', []).append(key)
    data['attempts'] = data.get('attempts', 0) + 1
    work['poe2Attempts'] = work.get('poe2Attempts', 0) + 1
    return None
