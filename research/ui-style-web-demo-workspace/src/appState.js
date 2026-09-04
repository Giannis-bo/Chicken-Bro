export const modeContent = {
  dialogue: {
    label: "对话",
    eyebrow: "和咕咕聊聊",
    title: "今天想先解决哪件事？",
    description: "把你的副本目标、装备疑问或输出困惑交给咕咕，先聊清楚再行动。",
    primaryAction: "开始对话",
    secondaryAction: "查看最近话题",
  },
  simulate: {
    label: "模拟",
    eyebrow: "进入战斗实验室",
    title: "让装备和输出先跑一遍",
    description: "选择角色、装备与战斗场景，先看到一份清晰的输出方向，再决定怎么调整。",
    primaryAction: "开始模拟",
    secondaryAction: "查看模拟说明",
  },
};

export const skinContent = {
  horde: {
    label: "为了部落！",
    sceneAsset: "/assets/horde-bg-v2-clean.png",
    cloudAsset: "/assets/horde-clouds-v2-clean.png",
    sceneOpacity: 0.44,
    cloudOpacity: 0.24,
    sceneFilter: "saturate(0.68) contrast(1.08)",
  },
};

export const petContent = {
  asset: "/assets/gu-gu-pet-v1.png",
  alt: "手绘卡通咕咕宠物",
  replayLabel: "让咕咕再掉一次",
};

export const workspaceContent = {
  newChatLabel: "新对话",
  recentLabel: "最近",
  emptyTitle: "准备好了，随时开始",
  emptyDescription: "把你的副本目标、装备疑问或输出困惑交给咕咕。",
  composerPlaceholder: "问问咕咕",
  quickPrompts: ["帮我看看元素萨满的装备", "从一个模拟开始", "聊聊咕咕的新皮肤"],
  history: [
    {
      id: "horde-background",
      label: "为了部落皮肤的画中画设计",
      preview: "咕咕掉入左栏，向右远眺背景",
      mode: "dialogue",
      messages: [
        { id: "horde-user", role: "user", text: "把为了部落皮肤做成有画中画感的页面背景。" },
        { id: "horde-assistant", role: "assistant", text: "可以，让咕咕从 Logo 掉入左侧栏，在右侧远眺背景插画。" },
      ],
    },
    {
      id: "elemental-setup",
      label: "元素萨满输出怎么调",
      preview: "装备、天赋与模拟入口",
      mode: "simulate",
      messages: [
        { id: "elemental-user", role: "user", text: "我想先跑一遍元素萨满的装备模拟。" },
        { id: "elemental-assistant", role: "assistant", text: "先锁定角色、装备和战斗场景，再开始一份可核对的模拟。" },
      ],
    },
    {
      id: "gugu-mascot",
      label: "咕咕宠物视觉设定",
      preview: "从 Logo 掉下来之后的陪伴感",
      mode: "dialogue",
      messages: [
        { id: "gugu-user", role: "user", text: "咕咕掉下来以后，希望它能留在左边陪着我。" },
        { id: "gugu-assistant", role: "assistant", text: "让它在左侧栏里慢慢落地，刚好向右看着你的对话。" },
      ],
    },
  ],
};

export function resolveMode(mode) {
  return mode === "simulate" ? "simulate" : "dialogue";
}

export function getModeContent(mode) {
  return modeContent[resolveMode(mode)];
}

export function resolveSkin(skin) {
  return Object.hasOwn(skinContent, skin) ? skin : "horde";
}

export function getSkinContent(skin) {
  return skinContent[resolveSkin(skin)];
}

export function getPetContent() {
  return petContent;
}

export function getWorkspaceContent() {
  return workspaceContent;
}
