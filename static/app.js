(() => {
  const $ = (sel) => document.querySelector(sel);
  const $$ = (sel) => Array.from(document.querySelectorAll(sel));

  const API = {
    trending: "/v1/trending-hashtags",
    build: "/v1/build-pack",
    job: (id) => `/v1/jobs/${encodeURIComponent(id)}`,
    pack: (id) => `/v1/packs/${encodeURIComponent(id)}`,
    ready: "/readyz",
  };

  const store = {
    get(k, d = null) {
      try { return JSON.parse(localStorage.getItem(k)) ?? d; } catch { return d; }
    },
    set(k, v) { localStorage.setItem(k, JSON.stringify(v)); },
    del(k) { localStorage.removeItem(k); },
  };

  const ui = {
    toast(msg) {
      const t = $("#toast");
      t.textContent = msg;
      t.style.display = "block";
      clearTimeout(ui._tt);
      ui._tt = setTimeout(() => (t.style.display = "none"), 2600);
    },
    setReady(ok) {
      const dot = $("#readyDot");
      const txt = $("#readyText");
      dot.classList.remove("good", "bad");
      if (ok) {
        dot.classList.add("good");
        txt.textContent = "READY";
      } else {
        dot.classList.add("bad");
        txt.textContent = "DOWN";
      }
    },
    setLast(jobId, packId) {
      $("#lastJob").textContent = jobId || "—";
      $("#lastPack").textContent = packId || "—";
    },
    setJobMeta({ jobId, status, progress, packId, polling }) {
      $("#jobId").textContent = `job: ${jobId || "—"}`;
      $("#packId").textContent = `pack: ${packId || "—"}`;
      $("#jobStatus").textContent = `status: ${status || "idle"}`;
      $("#jobEta").textContent = `polling: ${polling ? "on" : "off"}`;
      $("#jobBadge").textContent = status || "—";
      const pct = Math.max(0, Math.min(100, Math.round((progress || 0) * 100)));
      $("#progressFill").style.width = `${pct}%`;
    },
    setOutputs(pack) {
      const assets = pack?.assets || {};
      const genes = pack?.genes || {};
      const visual = pack?.visual || {};
      const dom = pack?.dominance || {};

      // LinkedIn
      $("#outLinkedIn").textContent = formatLinkedIn(assets.linkedin);
      $("#outX").textContent = formatX(assets.x);
      $("#outTikTok").textContent = formatTikTok(assets.tiktok);

      $("#outGenes").textContent = pretty(genes);
      $("#outVPrompt").textContent = (visual.prompt || "—");

      $("#outScore").textContent = pretty(dom);
      $("#scoreNum").textContent = (dom.score ?? "—");
      $("#scoreRec").textContent = (dom.recommendation || "—");
      $("#scoreWhy").textContent = Array.isArray(dom.reasons) ? dom.reasons.join(" • ") : "—";

      $("#outRaw").textContent = pretty(pack);

      // Image
      const imgBox = $("#imgBox");
      imgBox.innerHTML = "";
      if (visual.image_url) {
        const img = document.createElement("img");
        img.alt = "Generated image";
        img.loading = "lazy";
        img.referrerPolicy = "no-referrer";
        img.src = visual.image_url;
        imgBox.appendChild(img);
        $("#openImage").href = visual.image_url;
      } else {
        imgBox.innerHTML = `<div class="muted">—</div>`;
        $("#openImage").href = "#";
      }
    },
  };

  function pretty(obj) {
    try { return JSON.stringify(obj, null, 2); } catch { return String(obj); }
  }

  function formatLinkedIn(li) {
    if (!li) return "—";
    const h = li.headline ? `🟦 ${li.headline}\n\n` : "";
    const p = li.post || "";
    const tags = Array.isArray(li.hashtags) ? `\n\n${li.hashtags.join(" ")}` : "";
    return `${h}${p}${tags}`.trim();
  }

  function formatX(x) {
    if (!x) return "—";
    const t = x.tweet ? `🟦 Tweet:\n${x.tweet}\n\n` : "";
    const th = Array.isArray(x.thread) ? `🧵 Thread:\n- ${x.thread.join("\n- ")}` : "";
    return `${t}${th}`.trim() || "—";
  }

  function formatTikTok(tk) {
    if (!tk) return "—";
    const hook = tk.hook ? `🎬 Hook:\n${tk.hook}\n\n` : "";
    const s = Array.isArray(tk.script) ? `🗣 Script:\n- ${tk.script.join("\n- ")}\n\n` : "";
    const sh = Array.isArray(tk.shot_list) ? `🎥 Shot list:\n- ${tk.shot_list.join("\n- ")}` : "";
    return `${hook}${s}${sh}`.trim() || "—";
  }

  // Tabs
  function initTabs() {
    $$(".tab").forEach((b) => {
      b.addEventListener("click", () => {
        $$(".tab").forEach((x) => x.classList.remove("active"));
        $$(".tabpane").forEach((x) => x.classList.remove("active"));
        b.classList.add("active");
        $(`#${b.dataset.tab}`).classList.add("active");
      });
    });
  }

  // Sidebar navigation
  function initNav() {
    $$(".nav-item").forEach((b) => {
      b.addEventListener("click", () => {
        $$(".nav-item").forEach((x) => x.classList.remove("active"));
        b.classList.add("active");
        const view = b.dataset.view;
        $("#pageTitle").textContent = b.textContent.trim();
        $$(".view").forEach((v) => v.classList.remove("active"));
        $(`#view-${view}`).classList.add("active");
      });
    });
  }

  // Mode switch
  function initMode() {
    $$('input[name="mode"]').forEach((r) => {
      r.addEventListener("change", () => {
        const mode = getMode();
        $("#inputLabel").textContent = mode === "url" ? "ضع الرابط" : "اكتب النيش";
        $("#inputValue").placeholder = mode === "url"
          ? "مثال: https://www.linkedin.com/posts/..."
          : "مثال: التسويق بالذكاء الاصطناعي لشركات المقاولات";
      });
    });
  }

  function getMode() {
    const el = $('input[name="mode"]:checked');
    return el ? el.value : "niche";
  }

  function getPlatforms() {
    const checked = $$(".chip input[type=checkbox]:checked").map((x) => x.value);
    return checked.length ? checked : ["linkedin", "x", "tiktok"];
  }

  async function fetchJson(url, opts) {
    const r = await fetch(url, opts);
    const ct = r.headers.get("content-type") || "";
    if (!r.ok) {
      let body = "";
      try {
        body = ct.includes("application/json") ? JSON.stringify(await r.json()) : await r.text();
      } catch { body = ""; }
      throw new Error(`HTTP ${r.status}: ${body || "request failed"}`);
    }
    return ct.includes("application/json") ? await r.json() : await r.text();
  }

  // Trending
  async function loadTrending() {
    $("#trendsStatus").textContent = "Loading…";
    try {
      const data = await fetchJson(API.trending);
      const tags = data.hashtags || [];
      const box = $("#trendsBox");
      box.innerHTML = "";
      if (!tags.length) {
        box.innerHTML = `<div class="muted">لا توجد ترندات الآن.</div>`;
      } else {
        tags.forEach((t) => {
          const btn = document.createElement("button");
          btn.className = "tag";
          btn.type = "button";
          btn.textContent = t;
          btn.addEventListener("click", () => {
            const cur = $("#inputValue").value.trim();
            const add = cur ? `${cur} ${t}` : t;
            $("#inputValue").value = add;
            ui.toast("تمت إضافة هاشتاق للنيش.");
          });
          box.appendChild(btn);
        });
      }
      $("#trendsStatus").textContent = `OK • ${tags.length}`;
    } catch (e) {
      $("#trendsStatus").textContent = "Error";
      ui.toast(`فشل جلب الترندات: ${e.message}`);
    }
  }

  // Forge
  let pollTimer = null;
  let pollCount = 0;

  function stopPolling() {
    if (pollTimer) clearInterval(pollTimer);
    pollTimer = null;
    pollCount = 0;
    ui.setJobMeta({
      jobId: store.get("lastJobId"),
      status: "idle",
      progress: 0,
      packId: store.get("lastPackId"),
      polling: false
    });
  }

  function pollSettings() {
    const interval = Math.max(800, Number($("#pollInterval").value || 2000));
    const max = Math.max(10, Number($("#pollMax").value || 90));
    return { interval, max };
  }

  async function startPolling(jobId) {
    stopPolling();
    const { interval, max } = pollSettings();
    ui.setJobMeta({ jobId, status: "queued", progress: 0, packId: null, polling: true });

    pollTimer = setInterval(async () => {
      try {
        pollCount++;
        const job = await fetchJson(API.job(jobId));
        ui.setJobMeta({
          jobId,
          status: job.status,
          progress: job.progress || 0,
          packId: job.pack_id,
          polling: true
        });

        if (job.status === "done" && job.pack_id) {
          store.set("lastPackId", job.pack_id);
          ui.setLast(store.get("lastJobId"), store.get("lastPackId"));
          await loadPack(job.pack_id, jobId);
          ui.toast("تم توليد Pack بنجاح.");
          stopPolling();
        }

        if (job.status === "failed") {
          ui.toast(`فشل Job: ${job.error || "unknown error"}`);
          stopPolling();
        }

        if (pollCount >= max) {
          ui.toast("انتهت محاولات polling. شغّل tick أو أعد المحاولة.");
          stopPolling();
        }
      } catch (e) {
        // Keep polling a bit, but show toast occasionally
        if (pollCount % 8 === 0) ui.toast(`Polling error: ${e.message}`);
        if (pollCount >= max) stopPolling();
      }
    }, interval);
  }

  async function loadPack(packId, jobId = null) {
    const pack = await fetchJson(API.pack(packId));
    ui.setOutputs(pack);
    $("#jobBadge").textContent = "PACK";
    if (jobId) {
      store.set("lastJobId", jobId);
      store.set("lastPackId", packId);
    }
    ui.setLast(store.get("lastJobId"), store.get("lastPackId"));
  }

  async function forge() {
    const mode = getMode();
    const input = $("#inputValue").value.trim();
    if (!input) {
      ui.toast(mode === "url" ? "ضع رابطًا صحيحًا." : "اكتب نيشًا أولًا.");
      return;
    }

    const body = {
      mode,
      platforms: getPlatforms(),
      language: $("#language").value,
      tone: $("#tone").value,
      include_visual: $("#includeVisual").checked,
      sync: $("#syncMode").checked
    };

    if (mode === "url") body.url = input;
    else body.niche = input;

    $("#btnForge").disabled = true;
    $("#btnForge").textContent = "Forging…";
    try {
      const res = await fetchJson(API.build, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });

      // Async response (job)
      const jobId = res.job_id || res.job?.job_id || null;
      const packId = res.pack?.pack_id || null;

      if (jobId) {
        store.set("lastJobId", jobId);
        ui.setLast(store.get("lastJobId"), store.get("lastPackId"));
        ui.toast(`تم إنشاء Job: ${jobId}`);
        await startPolling(jobId);
      } else if (packId) {
        // Sync fallback
        store.set("lastPackId", packId);
        ui.setLast(store.get("lastJobId"), store.get("lastPackId"));
        ui.setOutputs(res.pack);
        ui.toast("تم توليد Pack (sync).");
      } else {
        ui.toast("استجابة غير متوقعة من السيرفر.");
      }
    } catch (e) {
      ui.toast(`فشل Forge: ${e.message}`);
    } finally {
      $("#btnForge").disabled = false;
      $("#btnForge").innerHTML = `<span class="spark">✦</span> Forge Dominance Pack`;
    }
  }

  // Copy
  async function copyText(text) {
    try {
      await navigator.clipboard.writeText(text);
      ui.toast("تم النسخ.");
    } catch {
      ui.toast("فشل النسخ. انسخ يدويًا.");
    }
  }

  function initCopy() {
    $$("[data-copy]").forEach((b) => {
      b.addEventListener("click", () => {
        const key = b.dataset.copy;
        let txt = "—";
        if (key === "linkedin") txt = $("#outLinkedIn").textContent;
        if (key === "x") txt = $("#outX").textContent;
        if (key === "tiktok") txt = $("#outTikTok").textContent;
        if (key === "genes") txt = $("#outGenes").textContent;
        if (key === "vprompt") txt = $("#outVPrompt").textContent;
        if (key === "score") txt = $("#outScore").textContent;
        if (key === "raw") txt = $("#outRaw").textContent;
        copyText(txt || "");
      });
    });
  }

  // Ready check
  async function refreshReady() {
    try {
      const r = await fetchJson(API.ready);
      ui.setReady(!!r.ready);
    } catch {
      ui.setReady(false);
    }
  }

  function initHotkeys() {
    document.addEventListener("keydown", (e) => {
      if ((e.ctrlKey || e.metaKey) && e.key === "Enter") {
        const forgeView = $("#view-forge");
        if (forgeView.classList.contains("active")) forge();
      }
    });
  }

  function initButtons() {
    $("#btnTrending").addEventListener("click", loadTrending);
    $("#btnForge").addEventListener("click", forge);
    $("#btnStopPoll").addEventListener("click", () => {
      stopPolling();
      ui.toast("تم إيقاف polling.");
    });

    $("#btnFetchLast").addEventListener("click", async () => {
      const pid = store.get("lastPackId");
      const jid = store.get("lastJobId");
      if (!pid) return ui.toast("لا يوجد Pack محفوظ.");
      ui.setJobMeta({ jobId: jid, status: "PACK", progress: 1, packId: pid, polling: false });
      await loadPack(pid, jid);
      ui.toast("تم تحميل آخر Pack.");
    });

    $("#btnRefresh").addEventListener("click", async () => {
      await refreshReady();
      ui.toast("تم التحديث.");
    });

    $("#btnClear").addEventListener("click", () => {
      store.del("lastJobId");
      store.del("lastPackId");
      ui.setLast(null, null);
      ui.setOutputs(null);
      ui.toast("تم المسح.");
    });

    $("#btnSaveUi").addEventListener("click", () => {
      store.set("ui.pollInterval", Number($("#pollInterval").value || 2000));
      store.set("ui.pollMax", Number($("#pollMax").value || 90));
      ui.toast("تم حفظ إعدادات الواجهة.");
    });
  }

  function loadUiSettings() {
    $("#pollInterval").value = store.get("ui.pollInterval", 2000);
    $("#pollMax").value = store.get("ui.pollMax", 90);
  }

  function boot() {
    initTabs();
    initNav();
    initMode();
    initCopy();
    initButtons();
    initHotkeys();
    loadUiSettings();

    // Restore last IDs
    const lj = store.get("lastJobId", null);
    const lp = store.get("lastPackId", null);
    ui.setLast(lj, lp);
    ui.setJobMeta({ jobId: lj, status: "idle", progress: 0, packId: lp, polling: false });

    refreshReady();
  }

  boot();
})();
