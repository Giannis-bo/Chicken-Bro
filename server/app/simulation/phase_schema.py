"""Shared public JSON schema for the phase experiment contract."""
_TOKEN={'type':'string','pattern':'^[a-zA-Z0-9][a-zA-Z0-9_]{0,79}$'}
_NUMBER={'type':'number','minimum':0,'maximum':10000000}
PHASE_SCHEMAS={
 'initialState':{'type':'object','additionalProperties':False,'description':'Compiler v7 phase start. Requires measurement. Resource max is resolved from this actor by the cloud engine. Buff remainingSeconds must be explicit or full (disclose full-duration assumption). Replaces the entire initialState on a base job. No hidden proc history, pets or DoTs are restored.', 'properties':{
  'resources':{'type':'object','maxProperties':32,'additionalProperties':{'anyOf':[_NUMBER,{'const':'max'}]}},
  'buffs':{'type':'object','maxProperties':32,'additionalProperties':{'type':'object','additionalProperties':False,'required':['stacks','remainingSeconds'],'properties':{
    'stacks':{'type':'integer','minimum':1,'maximum':100},'remainingSeconds':{'anyOf':[{'type':'number','exclusiveMinimum':0,'maximum':600},{'const':'full'}]}}}},
  'cooldowns':{'type':'object','maxProperties':32,'additionalProperties':{'type':'number','exclusiveMinimum':0,'maximum':600}}}},
 'measurement':{'type':'object','additionalProperties':False,'required':['durationSeconds'],'description':'Requires a complete actionLists.default; engine-generated rotations add precombat actions and are not allowed. Fixed phase at t=0; duration 20-120 seconds. Requires iterations <=128 (default32). Every iteration independently verifies state and counts requested actions. No custom precombat except snapshot_stats; sequence/strict_sequence wrappers are unsupported because reports hide child actions. Per-action withBuff means buff presence at execution, not proven damage amplification.', 'properties':{
  'durationSeconds':{'type':'integer','minimum':20,'maximum':120},
  'actions':{'type':'array','maxItems':16,'items':{'type':'object','additionalProperties':False,'required':['action'],'properties':{'action':_TOKEN,'buff':_TOKEN}}}}},
 'assertions':{'type':'object','additionalProperties':False,'description':'Required experiment conditions. A failed condition fails the job; inspect source/APL instead of claiming a comparison. Buff names are case-sensitive engine tokens (including potion suffixes). openingActions checks listed actions in report event order, ignoring other actions.', 'properties':{
  'openingActions':{'type':'array','minItems':1,'maxItems':16,'items':_TOKEN},
  'requiredBuffs':{'type':'array','minItems':1,'maxItems':16,'items':_TOKEN},
  'maxResourceOverflow':{'type':'object','maxProperties':32,'additionalProperties':_NUMBER}}}
}
