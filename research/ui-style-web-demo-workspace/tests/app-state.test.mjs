import assert from "node:assert/strict";
import test from "node:test";
import {
  getWorkspaceContent,
  getModeContent,
  getPetContent,
  getSkinContent,
  resolveMode,
  resolveSkin,
} from "../src/appState.js";

test("unknown entry modes resolve to the conversation journey", () => {
  assert.equal(resolveMode("unknown"), "dialogue");
  assert.equal(resolveMode(), "dialogue");
});

test("simulation journey exposes a clear primary action", () => {
  const content = getModeContent("simulate");

  assert.equal(content.label, "模拟");
  assert.equal(content.primaryAction, "开始模拟");
  assert.match(content.description, /装备|输出/);
});

test("the Horde skin exposes the scene and motion assets", () => {
  const skin = getSkinContent("horde");

  assert.equal(resolveSkin("horde"), "horde");
  assert.equal(resolveSkin("unknown"), "horde");
  assert.equal(skin.label, "为了部落！");
  assert.equal(skin.sceneAsset, "/assets/horde-bg-v2-clean.png");
  assert.equal(skin.cloudAsset, "/assets/horde-clouds-v2-clean.png");
});

test("the Horde scene keeps a visible low-saturation treatment", () => {
  const skin = getSkinContent("horde");

  assert.equal(skin.sceneOpacity, 0.44);
  assert.equal(skin.cloudOpacity, 0.24);
  assert.equal(skin.sceneFilter, "saturate(0.68) contrast(1.08)");
});

test("the Gugu pet exposes a transparent companion asset and replay label", () => {
  const pet = getPetContent();

  assert.equal(pet.asset, "/assets/gu-gu-pet-v1.png");
  assert.match(pet.alt, /咕咕/);
  assert.equal(pet.replayLabel, "让咕咕再掉一次");
});

test("the workspace content keeps the ChatGPT-style shell semantics", () => {
  const workspace = getWorkspaceContent();

  assert.equal(workspace.newChatLabel, "新对话");
  assert.equal(workspace.recentLabel, "最近");
  assert.equal(workspace.emptyTitle, "准备好了，随时开始");
  assert.equal(workspace.history.length, 3);
  assert.match(workspace.history[0].label, /为了部落/);
});
