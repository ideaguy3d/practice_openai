(() => {

    function attemp_1() {
        const chatkit = document.createElement("openai-chatkit");

        chatkit.setOptions({
            api: {
                url: "http://localhost:8000/chatkit",
                domainKey: "local-dev"
            }
        });

        chatkit.style.display = "block";
        chatkit.style.width = "360px";
        chatkit.style.height = "600px";

        document.getElementById("chat-root").appendChild(chatkit);
    }

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
    }

    async function start() {
        await initChatKit();
    }

    void start();

})();
