(() => {
  const params = new URLSearchParams(window.location.search);
  const variant = params.get("variant") || "original";
  const threadId = params.get("thread");
  const isCustomPage = window.location.pathname.endsWith("/custom_resume.html");

  function setTextById(id, value) {
    const el = document.getElementById(id);
    if (!el) {
      return;
    }
    el.textContent = value ?? "";
  }

  function applyResumeContent(content, targetIds) {
    if (!content || typeof content !== "object") {
      return;
    }

    const ids = Array.isArray(targetIds) ? targetIds : Object.keys(content);
    for (const id of ids) {
      if (Object.prototype.hasOwnProperty.call(content, id)) {
        setTextById(id, content[id]);
      }
    }
  }

  async function loadResumeData(url) {
    const response = await fetch(url, { cache: "no-store" });
    if (!response.ok) {
      throw new Error(`Failed to load ${url} (${response.status})`);
    }
    return response.json();
  }

  async function initOriginalResume() {
    setTextById("y", String(new Date().getFullYear()));

    try {
      let data;
      if ((variant === "custom" || isCustomPage) && threadId) {
        const encodedThread = encodeURIComponent(threadId);
        try {
          data = await loadResumeData(`/api/custom-resume/${encodedThread}`);
        } catch {
          data = await loadResumeData("/resume-content.json");
        }
      } else {
        data = await loadResumeData("/resume-content.json");
      }

      const content = data?.content ?? {};
      const targetIds = data?.target_ids ?? Object.keys(content);
      applyResumeContent(content, targetIds);
      window.RESUME_TARGET_IDS = targetIds;
      window.RESUME_CONTENT = content;
    } catch (error) {
      console.error("Could not load resume content JSON", error);
    }
  }

  window.applyResumeContent = (content) => applyResumeContent(content, window.RESUME_TARGET_IDS || []);
  window.setResumeField = setTextById;

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", () => {
      void initOriginalResume();
    });
  } else {
    void initOriginalResume();
  }
})();
