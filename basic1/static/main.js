(() => {

    const dom = {
        chatkitHost: document.getElementById("chatkit-host"),
    };

    async function waitForElementDefinition(elementName, timeoutMs) {
        console.log('PRE: in waitForElementDefinition()');
        await Promise.race([
            customElements.whenDefined(elementName),
            new Promise((_, reject) => {
                window.setTimeout(() => {
                    reject(new Error(`${elementName} was not defined before timeout`));
                }, timeoutMs);
            }),
        ]);
        console.log('POST: waitForElementDefinition()');
    }

    function add_event_listeners(chatkitElement) {
        chatkitElement.addEventListener("chatkit.ready", () => {
            console.log('ChatKit ready event');
        });

        chatkitElement.addEventListener("chatkit.thread.change", (event) => {
            const threadId = event.detail?.threadId ?? null;
            console.log('ChatKit thread change event');
            console.log(threadId);
        });

        chatkitElement.addEventListener("chatkit.response.end", () => {
            console.log('ChatKit response end event')
        });

        chatkitElement.addEventListener("chatkit.effect", (event) => {
            console.log('ChatKit effect event')
            console.log(event.detail);
        });

        chatkitElement.addEventListener("chatkit.error", (event) => {
            console.error("ChatKit error", event.detail?.error || event.detail);
        });
    }

    async function initChatKit() {
        if (!window.customElements) {
            setStatus("Browser does not support custom elements");
            return;
        }

        try {
            await waitForElementDefinition("openai-chatkit", 10000);
        }
        catch (error) {
            console.error("ChatKit custom element failed to define", error);
            return;
        }

        chatkitElement = document.createElement("openai-chatkit");

        dom.chatkitHost.appendChild(chatkitElement);

        chatkitElement.setOptions({
            api: {
                url: "/chatkit",
                domainKey: "local-dev",
            }
        });

        dom.chatkitHost.style.display = "block";
        dom.chatkitHost.style.width = "360px";
        dom.chatkitHost.style.height = "600px";
        add_event_listeners(chatkitElement);
    }

    async function start() {
        await initChatKit();

    }

    void start();

})();
