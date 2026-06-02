(function () {
  var DIMS = [
    { key: "stress", label: "\u538B\u529B" },
    { key: "fatigue", label: "\u75B2\u52B3" },
    { key: "anxiety", label: "\u7126\u8651" },
    { key: "sadness", label: "\u60B2\u4F24" },
    { key: "irritation", label: "\u6613\u6012" },
    { key: "focus", label: "\u4E13\u6CE8\u529B" },
    { key: "posture_tension", label: "\u59FF\u6001\u7D27\u5F20" },
    { key: "depression", label: "\u6291\u90C1\u503E\u5411" },
    { key: "emotional_stability", label: "\u60C5\u7EEA\u7A33\u5B9A\u6027" },
    { key: "eye_contact", label: "\u773C\u795E\u63A5\u89E6" },
    { key: "sleep_deficit_signs", label: "\u7761\u7720\u4E0D\u8DB3" },
    { key: "psychomotor_retardation", label: "\u7CBE\u795E\u8FD0\u52A8\u8FDF\u7F13" },
    { key: "positive_affect_blunting", label: "\u79EF\u6781\u60C5\u611F\u949D\u5316" },
  ];

  var history = [];
  var MAX_POINTS = 200;
  var vllmReady = false;
  var startedAt = null;
  var timerInterval = null;
  var isCollecting = false;
  var isAnalyzing = false;
  var lastResultCount = -1;

  var $ = function (s) { return document.querySelector(s); };
  var ring = $("#distressRing");
  var distressVal = $("#distressVal");
  var concernLevel = $("#concernLevel");
  var metaInfo = $("#metaInfo");
  var dimsEl = $("#dimensions");
  var notesCard = $("#notesCard");
  var exprText = $("#exprText");
  var postureText = $("#postureText");
  var recRow = $("#recRow");
  var recText = $("#recText");
  var guidanceCard = $("#guidanceCard");
  var guidanceContent = $("#guidanceContent");
  var canvas = $("#trendChart");
  var ctx = canvas.getContext("2d");
  var connStatus = $("#connStatus");
  var timerDisplay = $("#timerDisplay");
  var btnStart = $("#btnStart");
  var btnReset = $("#btnReset");
  var progressArea = $("#progressArea");
  var progressBar = $("#progressBar");
  var progressText = $("#progressText");
  var RING_CIRCUM = 326.7;

  function colorFor(v) {
    if (v < 2) return getComputedStyle(document.documentElement)
      .getPropertyValue("--green").trim() || "#2ecc71";
    if (v < 3) return getComputedStyle(document.documentElement)
      .getPropertyValue("--yellow").trim() || "#f1c40f";
    if (v < 4) return getComputedStyle(document.documentElement)
      .getPropertyValue("--orange").trim() || "#e67e22";
    return getComputedStyle(document.documentElement)
      .getPropertyValue("--red").trim() || "#e74c3c";
  }

  function buildDims() {
    dimsEl.innerHTML = DIMS.map(function (d) { return (
      '<div class="dim-item" id="dim-' + d.key + '">' +
        '<span class="dim-label">' + d.label + '</span>' +
        '<div class="dim-bar-wrap"><div class="dim-bar" id="bar-' + d.key + '" style="width:20%;background:#2ecc71"></div></div>' +
        '<span class="dim-val" id="val-' + d.key + '">--</span>' +
      '</div>'
    ); }).join("");
  }
  buildDims();

  function updateDims(result) {
    DIMS.forEach(function (d) {
      var v = result[d.key] || 1;
      var pct = (v / 5) * 100;
      var bar = document.getElementById("bar-" + d.key);
      var val = document.getElementById("val-" + d.key);
      if (bar) { bar.style.width = pct + "%"; bar.style.background = colorFor(v); }
      if (val) val.textContent = v.toFixed(1);
    });
  }

  function updateRing(v) {
    if (v === undefined || v === null) {
      ring.style.strokeDashoffset = RING_CIRCUM;
      distressVal.textContent = "--";
      return;
    }
    var pct = Math.min(v / 5, 1);
    var offset = RING_CIRCUM * (1 - pct);
    ring.style.strokeDashoffset = offset;
    ring.style.stroke = colorFor(v);
    distressVal.textContent = v.toFixed(1);
  }

  function drawChart() {
    var rect = canvas.parentElement.getBoundingClientRect();
    var dpr = window.devicePixelRatio || 1;
    var w = rect.width - 16;
    var h = 120;
    canvas.width = w * dpr;
    canvas.height = h * dpr;
    canvas.style.width = w + "px";
    canvas.style.height = h + "px";
    ctx.scale(dpr, dpr);

    ctx.clearRect(0, 0, w, h);
    if (history.length < 2) return;

    var hs = history.slice(-200);
    var pad = { top: 8, bottom: 16, left: 4, right: 4 };
    var cw = w - pad.left - pad.right;
    var ch = h - pad.top - pad.bottom;

    ctx.beginPath();
    hs.forEach(function (p, i) {
      var x = pad.left + (i / (hs.length - 1)) * cw;
      var y = pad.top + ch - ((p.v - 0.5) / 4.5) * ch;
      i === 0 ? ctx.moveTo(x, y) : ctx.lineTo(x, y);
    });
    ctx.strokeStyle = "#6c5ce7";
    ctx.lineWidth = 2;
    ctx.stroke();

    ctx.fillStyle = "#8b8fa3";
    ctx.font = "10px sans-serif";
    ctx.textAlign = "left";
    ctx.fillText("1 (\u5B89\u597D)", pad.left, h - 2);
    ctx.textAlign = "right";
    ctx.fillText("5 (\u4E25\u91CD)", w - pad.right, h - 2);

    ctx.strokeStyle = "#2d3154";
    ctx.lineWidth = 1;
    ctx.setLineDash([3, 3]);
    var avg = hs.reduce(function (s, p) { return s + p.v; }, 0) / hs.length;
    var avgY = pad.top + ch - ((avg - 0.5) / 4.5) * ch;
    ctx.beginPath();
    ctx.moveTo(pad.left, avgY);
    ctx.lineTo(w - pad.right, avgY);
    ctx.stroke();
    ctx.setLineDash([]);

    ctx.fillStyle = "#8b8fa3";
    ctx.font = "10px sans-serif";
    ctx.textAlign = "right";
    ctx.fillText("\u5E73\u5747 " + avg.toFixed(1), w - pad.right, avgY - 4);
  }

  function updateTimer() {
    if (!startedAt) { timerDisplay.textContent = "00:00"; return; }
    var elapsed = Math.floor((Date.now() - startedAt) / 1000);
    var m = String(Math.floor(elapsed / 60)).padStart(2, "0");
    var s = String(elapsed % 60).padStart(2, "0");
    timerDisplay.textContent = m + ":" + s;
  }

  function setButtonsState() {
    btnStart.disabled = !vllmReady || isCollecting || isAnalyzing;
    btnReset.disabled = isCollecting || isAnalyzing;
  }

  function resetUI() {
    updateRing(null);
    concernLevel.textContent = "--";
    metaInfo.textContent = "\u70B9\u51FB\u201C\u5F00\u59CB\u91C7\u96C6\u5206\u6790\u201D";
    notesCard.style.display = "none";
    document.getElementById("transcriptRow").style.display = "none";
    DIMS.forEach(function (d) {
      var bar = document.getElementById("bar-" + d.key);
      var val = document.getElementById("val-" + d.key);
      if (bar) { bar.style.width = "20%"; bar.style.background = "#2ecc71"; }
      if (val) val.textContent = "--";
    });
  }

  btnStart.addEventListener("click", function () {
    if (isCollecting || isAnalyzing) return;
    progressArea.style.display = "flex";
    progressBar.style.width = "0%";
    progressText.textContent = "\u51C6\u5907\u4E2D...";
    btnStart.disabled = true;
    isCollecting = true;

    if (!startedAt) { startedAt = Date.now(); updateTimer(); }
    if (!timerInterval) timerInterval = setInterval(updateTimer, 1000);

    fetch("/control", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ action: "start" })
    }).then(function (r) { return r.json(); }).catch(function () {});
  });

  btnReset.addEventListener("click", function () {
    history = [];
    drawChart();
    resetUI();
    fetch("/control", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ action: "reset" })
    }).catch(function () {});
  });

  function connectSSE() {
    var evtSource = new EventSource("/status");

    evtSource.onopen = function () {
      connStatus.textContent = "\u5DF2\u8FDE\u63A5";
      connStatus.style.borderColor = "#2ecc71";
      connStatus.style.color = "#2ecc71";
    };

    evtSource.onmessage = function (e) {
      try {
        var data = JSON.parse(e.data);

        vllmReady = data.vllm_ready === true;

        if (data.started_at) {
          startedAt = data.started_at * 1000;
          if (!timerInterval) timerInterval = setInterval(updateTimer, 1000);
        }

        if (data.vllm_ready === false) {
          connStatus.textContent = "\u7B49\u5F85\u5927\u6A21\u578B...";
          connStatus.style.borderColor = "#e67e22";
          connStatus.style.color = "#e67e22";
        } else if (data.vllm_ready === true && connStatus.textContent !== "\u5DF2\u8FDE\u63A5") {
          connStatus.textContent = "\u5DF2\u8FDE\u63A5";
          connStatus.style.borderColor = "#2ecc71";
          connStatus.style.color = "#2ecc71";
        }

        // Update collection state
        var state = data.collection_state || "idle";
        var pct = data.collection_progress || 0;

        if (state === "idle") {
          progressArea.style.display = "none";
          isCollecting = false;
          isAnalyzing = false;
          btnStart.textContent = "\u25B6 \u5F00\u59CB\u91C7\u96C6\u5206\u6790";
          setButtonsState();
        } else if (state === "collecting") {
          progressArea.style.display = "flex";
          progressBar.style.width = pct + "%";
          progressText.textContent = "\u91C7\u96C6\u4E2D " + Math.round(pct) + "%";
          isCollecting = true;
          btnStart.disabled = true;
        } else if (state === "analyzing") {
          progressArea.style.display = "flex";
          progressBar.style.width = "100%";
          progressBar.style.background = "linear-gradient(90deg, var(--accent), var(--orange))";
          progressText.textContent = "\u5206\u6790\u4E2D\u2026\u8BF7\u7A0D\u5019";
          isCollecting = false;
          isAnalyzing = true;
          btnStart.disabled = true;
        } else if (state === "done") {
          progressArea.style.display = "none";
          isCollecting = false;
          isAnalyzing = false;
          btnStart.textContent = "\u25B6 \u518D\u6B21\u91C7\u96C6\u5206\u6790";
          setButtonsState();
        }

        var currentCount = data.count || 0;
        if (currentCount > lastResultCount) {
          lastResultCount = currentCount;
          document.querySelector(".overall-card").classList.remove("result-fresh");
          void document.querySelector(".overall-card").offsetWidth;
          document.querySelector(".overall-card").classList.add("result-fresh");
        }

        var errorBanner = document.getElementById("errorBanner");

        if (data.result) {
          data.result._server_time = data.server_time;
          var r = data.result;

          if (r._error) {
            var em = r._error_message || "\u5206\u6790\u5931\u8D25";
            if (errorBanner) {
              errorBanner.style.display = "block";
              errorBanner.textContent = em;
            }
            return;
          }
          if (errorBanner) errorBanner.style.display = "none";
          notesCard.style.display = "block";
          var d = r.overall_distress || 0;
          updateRing(d);
          updateDims(r);

          var cl = r.concern_level || "low";
          var clMap = { low: "\u4F4E", medium: "\u4E2D", high: "\u9AD8" };
          concernLevel.textContent = "\u5173\u5207\u7EA7\u522B: " + (clMap[cl] || cl);
          concernLevel.style.color = colorFor(
            cl === "low" ? 1 : cl === "medium" ? 3 : 5
          );
          var elapsed = r._elapsed || 0;
          var frames = r._frames || 1;
          var ts = r._timestamp || "";
          var meta = "#" + (r._analysis_id || 0) + " | " + ts + " | " + frames + "\u5E27 | " + elapsed + "s";
          if (r._transcript) { meta += " | \u8F6C\u5199\u5DF2\u5305\u542B"; }
          metaInfo.textContent = meta;

            if (r.facial_expression || r.posture) {
              notesCard.style.display = "block";
              exprText.textContent = r.facial_expression || "--";
              postureText.textContent = r.posture || "--";
            if (r._transcript) {
              var trRow = document.getElementById("transcriptRow");
              trRow.style.display = "flex";
              document.getElementById("transcriptText").textContent = r._transcript.length > 120
                ? r._transcript.substring(0, 120) + "..."
                : r._transcript;
            }
            if (r.recommendation) {
              recRow.style.display = "flex";
              recText.textContent = r.recommendation;
            } else {
              recRow.style.display = "none";
            }

            var g = r._guidance;
            if (g) {
              guidanceCard.style.display = "block";
              var html = "";
              html += '<div class="guidance-header ' + (g.concern_title === "状态良好" ? "ok" : g.concern_title === "需要关注" ? "warn" : "alert") + '">';
              html += '<strong>' + g.concern_title + '</strong>：' + g.concern_message;
              html += '</div>';
              if (g.general_actions && g.general_actions.length) {
                html += '<div class="guidance-section"><div class="guidance-section-title">日常建议</div><ul>';
                g.general_actions.forEach(function(a) { html += '<li>' + a + '</li>'; });
                html += '</ul></div>';
              }
              if (g.specific_advice && g.specific_advice.length) {
                html += '<div class="guidance-section"><div class="guidance-section-title">针对性疏导建议</div><ul>';
                g.specific_advice.forEach(function(a) { html += '<li>' + a + '</li>'; });
                html += '</ul></div>';
              }
              if (g.crisis_message) {
                html += '<div class="crisis-message">' + g.crisis_message + '</div>';
              }
              guidanceContent.innerHTML = html;
            } else {
              guidanceContent.innerHTML = '<div class="guidance-placeholder">点击"开始采集分析"后，此处将显示个性化心理疏导建议</div>';
            }
          }

          history.push({ t: data.server_time, v: d });
          if (history.length > MAX_POINTS) history.splice(0, history.length - MAX_POINTS);
          drawChart();
        }
      } catch (err) {
        console.warn("SSE error:", err);
      }
    };

    evtSource.onerror = function () {
      connStatus.textContent = "\u91CD\u8FDE\u4E2D...";
      connStatus.style.borderColor = "#e67e22";
      connStatus.style.color = "#e67e22";
    };
  }

  setButtonsState();
  window.addEventListener("resize", drawChart);
  connectSSE();
})();
