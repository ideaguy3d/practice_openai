(() => {

    const dom = {
        chatkitHost: document.getElementById("chatkit-host"),
        resume2Panel: document.getElementById("resume-2-panel"),
        resume2Frame: document.getElementById("resume-2-frame"),
        resume2Status: document.getElementById("resume-2-status"),
        fallbackForm: document.getElementById("fallback-chat-form"),
        jobDescriptionInput: document.getElementById("job-description-input"),
        customizeButton: document.getElementById("customize-resume-button"),
        fallbackStatus: document.getElementById("fallback-chat-status"),
    };

    const state = {
        hasShownCustomizedResume: false,
        currentThreadId: null,
        pollTimer: null,
        pollAttemptsRemaining: 0,
        lastRenderedResumeKey: null,
    };

    async function wait_for_element_def(elementName, timeoutMs) {
        await Promise.race([
            customElements.whenDefined(elementName),
            new Promise((_, reject) => {
                window.setTimeout(() => {
                    reject(new Error(`${elementName} was not defined before timeout`));
                }, timeoutMs);
            }),
        ]);
    }

    function show_customized_resume(reason = "update", threadId = null, resumeKey = null) {
        if (!dom.resume2Panel || !dom.resume2Frame || !threadId) {
            return;
        }

        const renderKey = resumeKey || threadId;
        if (state.hasShownCustomizedResume && state.lastRenderedResumeKey === renderKey) {
            return;
        }

        state.currentThreadId = threadId;
        state.lastRenderedResumeKey = renderKey;

        if (!state.hasShownCustomizedResume) {
            dom.resume2Panel.classList.remove("is-hidden");
            state.hasShownCustomizedResume = true;
        }

        const encodedThread = encodeURIComponent(threadId);
        dom.resume2Frame.src = `/custom_resume.html?thread=${encodedThread}&t=${Date.now()}`;
        if (dom.resume2Status) {
            dom.resume2Status.textContent = `Loaded after ${reason}.`;
        }
    }

    function extract_thread_id(detail) {
        if (!detail || typeof detail !== "object") {
            return null;
        }

        return (
            detail.threadId ??
            detail.thread_id ??
            detail.thread?.id ??
            detail.thread?.threadId ??
            detail.item?.thread_id ??
            detail.item?.threadId ??
            null
        );
    }

    function effect_requests_resume_render(detail) {
        if (!detail) {
            return false;
        }

        const effectName =
            detail.effect ??
            detail.name ??
            detail.type ??
            detail.action ??
            detail.event ??
            null;

        if (typeof effectName === "string") {
            const normalized = effectName.toLowerCase();
            if (
                normalized.includes("render_resume_2") ||
                normalized.includes("show_resume_2") ||
                normalized.includes("resume_customized") ||
                normalized.includes("resume_updated")
            ) {
                return true;
            }
        }

        return Boolean(
            detail.render_resume_2 ||
            detail.show_resume_2 ||
            detail.resume_customized ||
            detail.resume_updated
        );
    }

    async function custom_resume_exists(threadId) {
        if (!threadId) {
            return false;
        }
        try {
            const response = await fetch(
                `/api/custom-resume/${encodeURIComponent(threadId)}/exists`, {
                method: "GET",
                cache: "no-store",
            });
            if (!response.ok) {
                return false;
            }
            const body = await response.json();
            return Boolean(body.exists);
        } catch (error) {
            console.error("Failed checking custom resume status", error);
            return false;
        }
    }

    async function latest_custom_resume() {
        try {
            const response = await fetch("/api/custom-resume/latest", {
                method: "GET",
                cache: "no-store",
            });
            if (!response.ok) {
                return null;
            }
            return await response.json();
        } catch (error) {
            console.error("Failed checking latest custom resume", error);
            return null;
        }
    }

    async function maybe_show_custom_resume(reason, allowLatestFallback = false) {
        const threadId = state.currentThreadId;
        if (allowLatestFallback) {
            const latest = await latest_custom_resume();
            if (latest?.thread_id) {
                show_customized_resume(reason, latest.thread_id, latest.updated_at);
                return true;
            }
        }

        if (threadId && await custom_resume_exists(threadId)) {
            show_customized_resume(reason, threadId);
            return true;
        }

        return false;
    }

    function stop_resume_polling() {
        if (state.pollTimer) {
            window.clearInterval(state.pollTimer);
            state.pollTimer = null;
        }
    }

    function start_resume_polling(reason) {
        state.pollAttemptsRemaining = 120;
        if (state.pollTimer) {
            return;
        }

        void maybe_show_custom_resume(reason, true);
        state.pollTimer = window.setInterval(() => {
            state.pollAttemptsRemaining -= 1;
            void maybe_show_custom_resume(reason, true);
            if (state.pollAttemptsRemaining <= 0) {
                stop_resume_polling();
            }
        }, 1500);
    }

    async function submit_fallback_job_description(event) {
        event.preventDefault();
        const jobDescription = dom.jobDescriptionInput?.value?.trim() ?? "";
        if (!jobDescription) {
            if (dom.fallbackStatus) {
                dom.fallbackStatus.textContent = "Paste a job description first.";
            }
            return;
        }

        if (dom.customizeButton) {
            dom.customizeButton.disabled = true;
        }
        if (dom.fallbackStatus) {
            dom.fallbackStatus.textContent = "Customizing resume...";
        }
        start_resume_polling("job description submission");

        try {
            const response = await fetch("/api/customize-resume", {
                method: "POST",
                headers: {
                    "Content-Type": "application/json",
                },
                cache: "no-store",
                body: JSON.stringify({
                    job_description: jobDescription,
                    thread_id: state.currentThreadId,
                }),
            });
            const body = await response.json().catch(() => ({}));
            if (!response.ok) {
                throw new Error(body.error || `Request failed (${response.status})`);
            }
            if (body.thread_id) {
                show_customized_resume("job description submission", body.thread_id, body.updated_at);
            } else {
                await maybe_show_custom_resume("job description submission", true);
            }
            if (dom.fallbackStatus) {
                dom.fallbackStatus.textContent = "Customized resume loaded.";
            }
        } catch (error) {
            console.error("Fallback resume customization failed", error);
            if (dom.fallbackStatus) {
                dom.fallbackStatus.textContent = "Could not customize resume. Check the server logs.";
            }
        } finally {
            if (dom.customizeButton) {
                dom.customizeButton.disabled = false;
            }
        }
    }

    function add_event_listeners(chatkitElement) {
        chatkitElement.addEventListener("chatkit.ready", () => {
            console.log('ChatKit ready event');
        });

        chatkitElement.addEventListener("chatkit.thread.change", (event) => {
            const threadId = extract_thread_id(event.detail);
            state.currentThreadId = threadId;
            console.log('ChatKit thread change event');
            console.log(threadId);
            void maybe_show_custom_resume("thread change", true);
        });

        chatkitElement.addEventListener("chatkit.response.end", () => {
            console.log('ChatKit response end event')
            void maybe_show_custom_resume("assistant response", true);
        });

        chatkitElement.addEventListener("chatkit.effect", (event) => {
            console.log('ChatKit effect event')
            console.log(event.detail);
            const threadId = extract_thread_id(event.detail);
            if (threadId) {
                state.currentThreadId = threadId;
            }
            if (effect_requests_resume_render(event.detail)) {
                void maybe_show_custom_resume("chatkit effect", true);
            }
        });

        chatkitElement.addEventListener("chatkit.error", (event) => {
            console.error("ChatKit error", event.detail?.error || event.detail);
        });

        chatkitElement.addEventListener("chatkit.response.start", () => {
            start_resume_polling("assistant response");
        });

        chatkitElement.addEventListener("chatkit.message.send", (event) => {
            const threadId = extract_thread_id(event.detail);
            if (threadId) {
                state.currentThreadId = threadId;
            }
            start_resume_polling("job description submission");
        });

        chatkitElement.addEventListener("keydown", () => {
            start_resume_polling("chat activity");
        });

        chatkitElement.addEventListener("pointerdown", () => {
            start_resume_polling("chat activity");
        });
    }

    async function init_chatkit() {
        if (!window.customElements) {
            console.error("Browser does not support custom elements");
            return;
        }

        try {
            await wait_for_element_def("openai-chatkit", 10000);
        }
        catch (error) {
            console.error("ChatKit element failed.", error);
            return;
        }

        let chatkitElement = document.createElement("openai-chatkit");

        dom.chatkitHost.appendChild(chatkitElement);

        chatkitElement.setOptions({
            api: {
                url: "/chatkit",
                domainKey: "local-dev",
            }
        });

        dom.chatkitHost.style.display = "block";
        dom.chatkitHost.style.width = "100%";
        dom.chatkitHost.style.height = "100%";
        add_event_listeners(chatkitElement);

        // Allows explicit function-call style triggers from future integrations.
        window.resumeCustomizerUI = {
            showCustomizedResume: () => {
                void maybe_show_custom_resume("manual function call", true);
            },
        };
        if (dom.fallbackForm) {
            dom.fallbackForm.addEventListener("submit", submit_fallback_job_description);
        }
        window.setTimeout(() => {
            if (chatkitElement.getAttribute("data-loaded") !== "true") {
                dom.chatkitHost.classList.add("is-hidden");
            }
        }, 4000);
        start_resume_polling("custom resume update");
    }

    async function start() {
        await init_chatkit();
    }

    void start();

})();
