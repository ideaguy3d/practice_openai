(() => {

    const dom = {
        chatkitHost: document.getElementById("chatkit-host"),
        resume2Panel: document.getElementById("resume-2-panel"),
        resume2Frame: document.getElementById("resume-2-frame"),
        resume2Status: document.getElementById("resume-2-status"),
    };

    const state = {
        hasShownCustomizedResume: false,
        currentThreadId: null,
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

    function show_customized_resume(reason = "update", threadId = null) {
        if (!dom.resume2Panel || !dom.resume2Frame || !threadId) {
            return;
        }

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

    async function maybe_show_custom_resume(reason) {
        const threadId = state.currentThreadId;
        if (!threadId) {
            return;
        }
        const exists = await custom_resume_exists(threadId);
        if (exists) {
            show_customized_resume(reason, threadId);
        }
    }

    function add_event_listeners(chatkitElement) {
        chatkitElement.addEventListener("chatkit.ready", () => {
            console.log('ChatKit ready event');
        });

        chatkitElement.addEventListener("chatkit.thread.change", (event) => {
            const threadId = event.detail?.threadId ?? null;
            state.currentThreadId = threadId;
            console.log('ChatKit thread change event');
            console.log(threadId);
            void maybe_show_custom_resume("thread change");
        });

        chatkitElement.addEventListener("chatkit.response.end", () => {
            console.log('ChatKit response end event')
            void maybe_show_custom_resume("assistant response");
        });

        chatkitElement.addEventListener("chatkit.effect", (event) => {
            console.log('ChatKit effect event')
            console.log(event.detail);
            if (effect_requests_resume_render(event.detail)) {
                void maybe_show_custom_resume("chatkit effect");
            }
        });

        chatkitElement.addEventListener("chatkit.error", (event) => {
            console.error("ChatKit error", event.detail?.error || event.detail);
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
                void maybe_show_custom_resume("manual function call");
            },
        };
    }

    async function start() {
        await init_chatkit();
    }

    void start();

})();
