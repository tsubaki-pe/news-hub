const tabs = document.querySelector("#tabs");
const newsRoot = document.querySelector("#news");
const statusEl = document.querySelector("#status");
const updatedEl = document.querySelector("#updated");
const feedHealthEl = document.querySelector("#feed-health");
const searchEl = document.querySelector("#search");
const categoryTemplate = document.querySelector("#category-template");
const itemTemplate = document.querySelector("#item-template");

const NEWS_URL = "./news.json";
let newsData;
let activeCategoryId = "world";
let searchQuery = "";

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
  return Number.isNaN(date.getTime()) ? fallback : dateTimeFormatter.format(date);
}

function formatUpdatedAt(value) {
  if (!value) return "更新日時不明";
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? "更新日時不明" : `最終更新 ${fullDateTimeFormatter.format(date)}`;
}

function validateNews(data) {
  if (!data || !Array.isArray(data.categories)) {
    throw new Error("news.json の categories 配列が見つかりません。");
  }
  data.categories.forEach((category) => {
    if (!category.id || !category.name || !Array.isArray(category.items)) {
      throw new Error("news.json に不正なカテゴリがあります。");
    }
  });
}

function matchesSearch(item) {
  if (!searchQuery) return true;
  return [item.title, item.source, item.excerpt].some((value) =>
    String(value || "").toLocaleLowerCase("ja").includes(searchQuery),
  );
}

function setActiveTab(categoryId) {
  document.querySelectorAll(".tab-button").forEach((button) => {
    const selected = button.dataset.category === categoryId;
    button.classList.toggle("is-active", selected);
    button.setAttribute("aria-selected", String(selected));
    button.tabIndex = selected ? 0 : -1;
  });
}

function createEmptyMessage() {
  const message = document.createElement("p");
  message.className = "empty";
  message.textContent = searchQuery
    ? "条件に一致するニュースはありません。"
    : "このカテゴリにはまだ記事がありません。次回の自動更新後に表示されます。";
  return message;
}

function renderCategory(categoryId) {
  const category = newsData.categories.find((item) => item.id === categoryId);
  if (!category) return;

  activeCategoryId = categoryId;
  setActiveTab(categoryId);
  newsRoot.textContent = "";

  const visibleItems = category.items.filter(matchesSearch);
  const panel = categoryTemplate.content.firstElementChild.cloneNode(true);
  panel.dataset.category = categoryId;
  panel.querySelector("h2").textContent = category.name;
  panel.querySelector(".count").textContent = searchQuery
    ? `${visibleItems.length} / ${category.items.length}件`
    : `${category.items.length}件`;

  const itemsRoot = panel.querySelector(".items");
  if (!visibleItems.length) itemsRoot.append(createEmptyMessage());

  visibleItems.forEach((item) => {
    const itemNode = itemTemplate.content.firstElementChild.cloneNode(true);
    itemNode.href = item.link;
    itemNode.querySelector(".source").textContent = item.source;
    itemNode.querySelector("time").textContent = formatDate(item.publishedAt, "日時不明");
    itemNode.querySelector("time").dateTime = item.publishedAt || "";
    itemNode.querySelector("strong").textContent = item.title;
    itemNode.querySelector(".excerpt").textContent = item.excerpt || "要約はありません。";
    itemsRoot.append(itemNode);
  });

  newsRoot.append(panel);
}

function renderTabs(categories) {
  tabs.textContent = "";
  categories.forEach((category) => {
    const button = document.createElement("button");
    button.className = "tab-button";
    button.type = "button";
    button.dataset.category = category.id;
    button.setAttribute("role", "tab");
    button.textContent = category.name;
    button.addEventListener("click", () => renderCategory(category.id));
    tabs.append(button);
  });
}

function render(data) {
  validateNews(data);
  newsData = data;
  updatedEl.textContent = formatUpdatedAt(data.generatedAt);
  feedHealthEl.textContent = data.errors?.length
    ? `${data.errors.length}件の配信元を取得できませんでした`
    : "すべての配信元を取得済み";
  feedHealthEl.classList.toggle("has-errors", Boolean(data.errors?.length));
  renderTabs(data.categories);

  if (!data.categories.some((category) => category.id === activeCategoryId)) {
    activeCategoryId = data.categories[0]?.id;
  }
  if (activeCategoryId) renderCategory(activeCategoryId);
  statusEl.hidden = true;
}

searchEl.addEventListener("input", () => {
  searchQuery = searchEl.value.trim().toLocaleLowerCase("ja");
  if (newsData) renderCategory(activeCategoryId);
});

async function loadNews() {
  try {
    const response = await fetch(NEWS_URL, { cache: "no-store" });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    render(await response.json());
  } catch (error) {
    statusEl.hidden = false;
    statusEl.textContent = `ニュースを読み込めませんでした: ${error.message}`;
    updatedEl.textContent = "読み込み失敗";
    console.error(error);
  }
}

loadNews();
