import { useState } from "react";
import {
  getModeContent,
  getPetContent,
  getSkinContent,
  getWorkspaceContent,
  resolveMode,
} from "./appState.js";

const modes = [
  { id: "dialogue", number: "01", label: "对话" },
  { id: "simulate", number: "02", label: "模拟" },
];

const hordeSkin = getSkinContent("horde");
const guguPet = getPetContent();
const workspace = getWorkspaceContent();
const historyContent = workspace.history;

function createAssistantReply(mode) {
  return mode === "simulate"
    ? "咕咕收到了。下一步可以锁定角色、装备和战斗场景。"
    : "咕咕收到了。我们先把问题拆开，再一起算清楚。";
}

export function App() {
  const [mode, setMode] = useState("dialogue");
  const [isHordeSkin, setIsHordeSkin] = useState(true);
  const [petRun, setPetRun] = useState(0);
  const [isPetLanded, setIsPetLanded] = useState(false);
  const [activeHistoryId, setActiveHistoryId] = useState("new");
  const [messages, setMessages] = useState([]);
  const [draft, setDraft] = useState("");
  const [notice, setNotice] = useState("咕咕已经在左侧栏里，等你开口。");
  const content = getModeContent(mode);

  function selectMode(nextMode) {
    const safeMode = resolveMode(nextMode);
    setMode(safeMode);
    setNotice(
      safeMode === "simulate"
        ? "模拟入口已准备好，先从你的角色开始。"
        : "对话入口已准备好，先把问题说给咕咕。",
    );
  }

  function startNewChat() {
    setActiveHistoryId("new");
    setMessages([]);
    setDraft("");
    setMode("dialogue");
    setNotice("新对话已准备好，咕咕在左侧栏等你。");
  }

  function openHistory(item) {
    setActiveHistoryId(item.id);
    setMessages(item.messages);
    setDraft("");
    setMode(resolveMode(item.mode));
    setNotice(`已打开：${item.label}`);
  }

  function submitMessage(event) {
    event.preventDefault();
    const trimmed = draft.trim();

    if (!trimmed) {
      return;
    }

    const stamp = Date.now();
    setMessages((current) => [
      ...current,
      { id: `user-${stamp}`, role: "user", text: trimmed },
      { id: `assistant-${stamp}`, role: "assistant", text: createAssistantReply(mode) },
    ]);
    setDraft("");
    setNotice(mode === "simulate" ? "模拟入口已准备好。" : "咕咕正在对话区回复你。");
  }

  function handleQuickPrompt(prompt) {
    setDraft(prompt);
    setNotice("已经把这句话放进输入框，确认后发给咕咕。");
  }

  function toggleHordeSkin() {
    const nextIsHordeSkin = !isHordeSkin;
    setIsHordeSkin(nextIsHordeSkin);

    if (nextIsHordeSkin) {
      setIsPetLanded(false);
      setPetRun((current) => current + 1);
      setNotice("为了部落主题已开启，咕咕从 Logo 位置落下。 ");
    } else {
      setIsPetLanded(false);
      setNotice("主题背景已收起，回到清爽对话界面。");
    }
  }

  function replayPet() {
    setIsPetLanded(false);
    setPetRun((current) => current + 1);
    setNotice("咕咕又从 Logo 位置落下来了。");
  }

  function handlePetAnimationEnd(event) {
    if (event.animationName === "pet-sidebar-drop") {
      setIsPetLanded(true);
    }
  }

  return (
    <div className={`prototype-shell ${isHordeSkin ? "skin-horde" : ""}`} id="top">
      <header className="site-header">
        <a className="brand-lockup" href="#top" aria-label="炸鸡队长来啦首页">
          <span className="brand-mascot-frame">
            <img className="brand-mascot" src="/assets/gu-gu-mascot.png" alt="手绘卡通咕咕" />
          </span>
          <span className="brand-name">炸鸡队长来啦</span>
        </a>

        <nav className="mode-switch" aria-label="工作入口">
          {modes.map((item) => (
            <button
              className={`mode-switch-item ${mode === item.id ? "is-active" : ""}`}
              key={item.id}
              type="button"
              aria-pressed={mode === item.id}
              onClick={() => selectMode(item.id)}
            >
              <span className="mode-switch-number">{item.number}</span>
              <span>{item.label}</span>
            </button>
          ))}
        </nav>

        <div className="header-actions">
          <button
            className={`skin-toggle ${isHordeSkin ? "is-active" : ""}`}
            type="button"
            aria-pressed={isHordeSkin}
            aria-label={isHordeSkin ? "关闭为了部落主题" : "开启为了部落主题"}
            onClick={toggleHordeSkin}
          >
            <span className="skin-toggle-dot" aria-hidden="true" />
            <span className="skin-toggle-label">{isHordeSkin ? hordeSkin.label : "开启主题"}</span>
          </button>
          <button
            className="header-menu"
            type="button"
            aria-label="打开更多设置"
            onClick={() => setNotice("更多设置将在后续版本开放。")}
          >
            <span aria-hidden="true">•••</span>
          </button>
        </div>
      </header>

      <div className="workspace-shell">
        <aside className="history-sidebar" aria-label="历史对话">
          <div className="sidebar-content">
            <button className={`new-chat-button ${activeHistoryId === "new" ? "is-active" : ""}`} type="button" onClick={startNewChat}>
              <span className="control-glyph" aria-hidden="true">＋</span>
              <span>{workspace.newChatLabel}</span>
            </button>

            <div className="history-heading">
              <span>{workspace.recentLabel}</span>
              <span className="history-count">{historyContent.length}</span>
            </div>

            <div className="history-list">
              {historyContent.map((item) => (
                <button
                  className={`history-item ${activeHistoryId === item.id ? "is-active" : ""}`}
                  key={item.id}
                  type="button"
                  aria-pressed={activeHistoryId === item.id}
                  onClick={() => openHistory(item)}
                >
                  <span className="history-item-label">{item.label}</span>
                  <span className="history-item-preview">{item.preview}</span>
                </button>
              ))}
            </div>
          </div>

          <div className="sidebar-account">
            <span className="account-avatar" aria-hidden="true">咕</span>
            <span className="account-copy">
              <strong>咕咕用户</strong>
              <small>Web demo</small>
            </span>
            <span className="account-more" aria-hidden="true">•••</span>
          </div>

          {isHordeSkin ? (
            <div
              className={`pet-stage ${isPetLanded ? "is-settled" : ""}`}
              data-pet-state={isPetLanded ? "settled" : "falling"}
              key={petRun}
              onAnimationEnd={handlePetAnimationEnd}
            >
              <button className="pet-button" type="button" aria-label={guguPet.replayLabel} onClick={replayPet}>
                <img className="pet-mascot" src={guguPet.asset} alt={guguPet.alt} />
              </button>
              <span className="pet-caption" aria-hidden="true">
                {isPetLanded ? "咕咕 · 远眺中" : "咕咕落下中"}
              </span>
            </div>
          ) : null}
        </aside>

        <main className="chat-main" id="journey">
          {isHordeSkin ? (
            <div
              className="chat-art-layer"
              aria-hidden="true"
              style={{
                "--scene-opacity": hordeSkin.sceneOpacity,
                "--cloud-opacity": hordeSkin.cloudOpacity,
                "--scene-filter": hordeSkin.sceneFilter,
              }}
            >
              <div className="chat-art-crop">
                <img className="chat-scene" src={hordeSkin.sceneAsset} alt="" />
                <div className="chat-art-wash" />
                <img className="chat-cloud chat-cloud-back" src={hordeSkin.cloudAsset} alt="" />
                <img className="chat-cloud chat-cloud-front" src={hordeSkin.cloudAsset} alt="" />
              </div>
            </div>
          ) : null}

          <div className="chat-topbar">
            <div className="chat-title-group">
              <span className="chat-title">咕咕助手</span>
              <span className="chat-status"><span className="chat-status-dot" aria-hidden="true" />在线</span>
            </div>
            <div className="chat-context">
              <span>{content.label}</span>
              <span className="chat-context-divider" aria-hidden="true">/</span>
              <span className="chat-context-muted">{isHordeSkin ? "为了部落主题" : "清爽工作台"}</span>
            </div>
          </div>

          <section className={`chat-scroll ${messages.length ? "has-messages" : ""}`} aria-live="polite">
            {messages.length ? (
              <div className="message-list">
                {messages.map((message) => (
                  <div className={`message-row message-${message.role}`} key={message.id}>
                    <div className="message-meta">{message.role === "assistant" ? "咕咕" : "你"}</div>
                    <div className="message-bubble">{message.text}</div>
                  </div>
                ))}
              </div>
            ) : (
              <div className="empty-state">
                <p className="empty-eyebrow">WOW COMPANION <span aria-hidden="true">/</span> {content.label}</p>
                <h1>{workspace.emptyTitle}</h1>
                <p className="empty-description">
                  {mode === "simulate" ? content.description : workspace.emptyDescription}
                </p>
                <div className="empty-hint">
                  <span className="empty-hint-dot" aria-hidden="true" />
                  <span>{content.title}</span>
                </div>
              </div>
            )}
          </section>

          <div className="chat-compose-area">
            <p className="chat-notice" aria-live="polite">{notice}</p>
            <form className="composer" onSubmit={submitMessage}>
              <button className="composer-add" type="button" aria-label="添加内容">＋</button>
              <input
                value={draft}
                onChange={(event) => setDraft(event.target.value)}
                aria-label="输入消息"
                placeholder={mode === "simulate" ? "输入角色、装备或战斗场景" : workspace.composerPlaceholder}
              />
              <button
                className="composer-mode"
                type="button"
                aria-label={`切换到${mode === "dialogue" ? "模拟" : "对话"}`}
                onClick={() => selectMode(mode === "dialogue" ? "simulate" : "dialogue")}
              >
                <span>{content.label}</span>
                <span aria-hidden="true">⌄</span>
              </button>
              <button className="composer-send" type="submit" aria-label="发送消息" disabled={!draft.trim()}>
                ↑
              </button>
            </form>

            {!messages.length ? (
              <div className="quick-prompts" aria-label="快速开始">
                {workspace.quickPrompts.map((prompt) => (
                  <button className="quick-prompt" type="button" key={prompt} onClick={() => handleQuickPrompt(prompt)}>
                    {prompt}
                  </button>
                ))}
              </div>
            ) : null}

            <p className="composer-footnote">咕咕可能会犯错，请核对重要信息。</p>
          </div>
        </main>
      </div>
    </div>
  );
}
