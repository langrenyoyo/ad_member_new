/* No SDK, tracking pixels or authentication tokens in invitation URLs/storage. */
"use strict";
(() => {
  const $ = id => document.getElementById(id);
  const query = new URLSearchParams(location.search);
  const gameId = Number(query.get("game_id"));
  const inviteCode = (query.get("invite_code") || "").trim().toUpperCase();
  let invitation = null, challenge = null, busy = false, retryAt = 0, deviceId;
  try {
    deviceId = sessionStorage.getItem("invite-device");
    if (!deviceId) { deviceId = "web-" + crypto.randomUUID(); sessionStorage.setItem("invite-device", deviceId); }
  } catch { deviceId = "web-" + Date.now() + "-" + Math.random().toString(36).slice(2); }
  const status = text => { $("status").textContent = text; };
  function updateButtons() {
    $("send-code").disabled = busy || !invitation || !$("consent").checked || Date.now() < retryAt;
    $("login").disabled = busy || !invitation || !$("consent").checked || !challenge;
    $("send-code").textContent = Date.now() < retryAt ? Math.ceil((retryAt - Date.now()) / 1000) + "秒后重发" : "获取验证码";
  }
  async function api(path, body) {
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 20000);
    try {
      const response = await fetch("/api/app/v1/" + path, {
        method: body ? "POST" : "GET", credentials: "omit", cache: "no-store", signal: controller.signal,
        headers: body ? {"Content-Type":"application/json"} : {}, body: body ? JSON.stringify(body) : undefined
      });
      let json;
      try { json = await response.json(); }
      catch { throw new Error("服务暂不可用，请稍后重试。"); }
      if (!response.ok) {
        const detail = json.detail;
        throw new Error(typeof detail === "string" ? detail : detail?.message || "请求失败，请稍后重试");
      }
      return json.data;
    } finally { clearTimeout(timeout); }
  }
  function safeDownload(value) {
    if (!value) return null;
    const url = new URL(value, location.origin);
    return url.protocol === "https:" || (url.origin === location.origin && url.pathname.startsWith("/downloads/")) ? url.href : null;
  }
  async function load() {
    invitation = null; $("retry").hidden = true; updateButtons();
    if (!Number.isSafeInteger(gameId) || gameId < 1 || !/^[A-Z0-9]{6}$/.test(inviteCode)) {
      status("邀请链接不完整，请向邀请人获取新的链接。"); return;
    }
    try {
      invitation = await api("invitations/resolve?" + new URLSearchParams({game_id:gameId,invite_code:inviteCode}));
      $("invite-code").textContent = invitation.invite_code;
      $("copy-code").disabled = false;
      $("eligibility").textContent = invitation.registration_eligible ? "团长或代理邀请码，可按规则绑定邀请关系。" :
        "普通会员邀请码不具备强制邀请码注册资格。新用户请联系团长或代理获取有效邀请码；已有账号可继续登录。";
      const openUrl = invitation.app_open_url || "";
      const validOpenUrl = /^(hehe|guangjiyexing|yazhiyiji):\/\/invite\?/.test(openUrl);
      $("open-app").hidden = !validOpenUrl;
      if (validOpenUrl) $("open-app").href = openUrl;
      const download = safeDownload(invitation.download_url);
      if (download) { $("download").href = download; $("download").hidden = false; }
      $("download-note").textContent = download ? "请保存本页或邀请码，以便安装后继续。" : "下载包暂未发布，请联系运营方获取安装包。";
      status("邀请链接已验证，请选择浏览器登录或下载 APP。");
      const policy = await api("policy?game_id=" + gameId);
      $("announcement").textContent = policy.announcement ? "公告：" + policy.announcement : "";
    } catch (error) { invitation = null; status(error.name === "AbortError" ? "网络超时，请重试。" : error.message); $("retry").hidden = false; }
    updateButtons();
  }
  $("send-code").onclick = async () => {
    if (busy || !invitation || !$("consent").checked || Date.now() < retryAt) return;
    const phone = $("phone").value.trim();
    if (!/^1[3-9][0-9]{9}$/.test(phone)) { status("请输入有效的11位手机号。"); return; }
    busy = true; updateButtons();
    try {
      const data = await api("auth/sms/send", {phone,game_id:gameId});
      challenge = {id:data.challenge_id,phone}; retryAt = Date.now() + 60000;
      status("验证码已发送，5分钟内有效。");
    } catch(error) { status(error.name === "AbortError" ? "请求超时，请稍后重试。" : error.message); }
    finally { busy = false; updateButtons(); }
  };
  $("phone").oninput = () => { if (challenge && challenge.phone !== $("phone").value.trim()) challenge = null; updateButtons(); };
  $("consent").onchange = updateButtons;
  $("login-form").onsubmit = async event => {
    event.preventDefault();
    if (busy || !invitation || !challenge || !$("consent").checked) return;
    const phone = $("phone").value.trim(), code = $("sms-code").value.trim();
    if (phone !== challenge.phone || !/^[0-9]{6}$/.test(code)) { status("请获取当前手机号验证码，并输入6位验证码。"); return; }
    busy = true; updateButtons();
    try {
      await api("auth/sms/login", {phone,code,challenge_id:challenge.id,game_id:gameId,device_id:deviceId,platform:"web",
        invite_code:invitation.registration_eligible ? inviteCode : ""});
      challenge = null; $("sms-code").value = "";
      status("注册 / 登录成功！请安装或打开 APP，使用同一手机号验证码登录继续，邀请关系已按后台规则处理。");
    } catch(error) { status(error.name === "AbortError" ? "请求超时，请重新获取验证码后重试。" : error.message); }
    finally { busy = false; updateButtons(); }
  };
  $("copy-code").onclick = async () => {
    try { await navigator.clipboard.writeText(inviteCode); status("邀请码已复制。"); }
    catch { status("请长按选择邀请码并复制：" + inviteCode); }
  };
  $("retry").onclick = load;
  setInterval(updateButtons, 1000);
  load();
})();
