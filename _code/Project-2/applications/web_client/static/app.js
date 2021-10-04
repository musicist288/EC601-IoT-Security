(function () {
    let data = { topics: [] };

    async function loadDocument() {
        let response = await window.fetch("/api/topics");
        if (response.status != 200) {
            console.error("Error loading topics.");
            return;
        }

        let topics = (await response.json())['topics'];
        data.topics = topics.map((t) => t.name);
        $(".topics-search").typeahead({
            source: data.topics
        })
    }

    async function search_for_users(topic) {
        let query = "?topic=" + encodeURIComponent(topic)
        let response = await window.fetch("/api/user-topics" + query);
        if (response.status != 200) {
            console.error("Error querying for topic.");
            return;
        }

        let user_topics = (await response.json())['data'];
        let results = document.querySelector(".results");
        for (let child of results.childNodes) {
            results.removeChild(child);
        }

        for (let user of user_topics[topic]) {
            let div = document.createElement("div");
            div.classList.add("result");
            div.innerHTML = `
                <span class="name">${user.name}</span>
                    <a href="https://twitter.com/${user.username}" target="_blank" class="url">
                        <span class="username">(@${user.username})</span>
                    </a>
                <span class="description">${user.description}</span>

            `;
            results.appendChild(div);
        }
    }

    document.addEventListener("DOMContentLoaded", loadDocument);
    $(document).on('input', '.topics-search', function (evt) {
        let val = evt.target.value.trim()
        if (data.topics.indexOf(val) > -1) {
            search_for_users(val);
        }
    });
})();
