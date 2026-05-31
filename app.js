const tabs = document.querySelector("#tabs");
const newsRoot = document.querySelector("#news");
const statusEl = document.querySelector("#status");
const updatedEl = document.querySelector("#updated");
const categoryTemplate = document.querySelector("#category-template");
const itemTemplate = document.querySelector("#item-template");

const dateTimeFormatter = new Intl.DateTimeFormat("ja-JP", {
  month: "numeric",
  day: "numeric",
  hour: "2-digit",
  minute: "2-digit",
});

const fullDateTimeFormatter = new Intl.DateTimeFormat("ja-JP", {
  year: "numeric",
  month: "numeric",
  day: "numeric",
  hour: "2-digit",
  minute: "2-digit",
  timeZoneName: "short",
});

function formatDate(value, fallback = "") {
  if (!value) return fallback;
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return dateTimeFormatter.format(date);
}

function formatUpdatedAt(value) {
  if (!value) return "初回更新待ち";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "更新日時不明";
  return `最終更新 ${fullDateTimeFormatter.format(date)}`;
}

function showCategory(id) {
  document.querySelectorAll(".category-panel").forEach((panel) => {
    panel.hidden = panel.dataset.category !== id;
  });
  document.querySelectorAll(".tab-button").forEach((button) => {
    const selected = button.dataset.category === id;
    button.classList.toggle("is-active", selected);
    button.setAttribute("aria-selected", String(selected));
  });
}

function createEmptyMessage() {
  const message = document.createElement("p");
  message.className = "empty";
  message.textContent = "このカテゴリはまだ記事がありません。次回の自動更新後に表示されます。";
  return message;
}

function render(data) {
  newsRoot.textContent = "";
  tabs.textContent = "";
  updatedEl.textContent = formatUpdatedAt(data.generatedAt);

  data.categories.forEach((category, index) => {
    const button = document.createElement("button");
    button.className = "tab-button";
    button.type = "button";
    button.dataset.category = category.id;
    button.setAttribute("role", "tab");
    button.textContent = category.name;
    button.addEventListener("click", () => showCategory(category.id));
    tabs.append(button);

    const panel = categoryTemplate.content.firstElementChild.cloneNode(true);
    panel.dataset.category = category.id;
    panel.hidden = index !== 0;
    panel.querySelector("h2").textContent = category.name;
    panel.querySelector(".count").textContent = `${category.items.length}件`;

    const itemsRoot = panel.querySelector(".items");
    if (!category.items.length) {
      itemsRoot.append(createEmptyMessage());
    }

    category.items.forEach((item) => {
      const itemNode = itemTemplate.content.firstElementChild.cloneNode(true);
      itemNode.href = item.link;
      itemNode.querySelector(".source").textContent = item.source;
      itemNode.querySelector("time").textContent = formatDate(item.publishedAt, "日時不明");
      itemNode.querySelector("time").dateTime = item.publishedAt || "";
      itemNode.querySelector("strong").textContent = item.title;
      itemNode.querySelector(".excerpt").textContent = item.excerpt || "抜粋はありません。";
      itemsRoot.append(itemNode);
    });

    newsRoot.append(panel);
  });

  statusEl.hidden = true;
  if (data.categories.length) {
    showCategory(data.categories[0].id);
  }
}

async function loadNews() {
  try {
    const response = await fetch("data/news.json", { cache: "no-store" });
    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`);
    }
    const data = await response.json();
    render(data);
  } catch (error) {
    statusEl.textContent = "ニュースを読み込めませんでした。しばらくしてから再読み込みしてください。";
    updatedEl.textContent = "読み込み失敗";
    console.error(error);
  }
}

loadNews();
