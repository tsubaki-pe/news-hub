const tabs = document.querySelector("#tabs");
const newsRoot = document.querySelector("#news");
const statusEl = document.querySelector("#status");
const updatedEl = document.querySelector("#updated");
const categoryTemplate = document.querySelector("#category-template");
const itemTemplate = document.querySelector("#item-template");

const NEWS_URL = "./news.json";
const CATEGORY_IDS = {
  "世界ニュース": "world",
  "日本ニュース": "japan",
  "投資ニュース": "investment",
  "AIニュース": "ai",
  "教育ニュース": "education",
};

let newsData = null;
let activeCategoryId = "world";

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

function normalizeCategoryId(category) {
  if (category.id === "investing") return "investment";
  return CATEGORY_IDS[category.name] || category.id;
}

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

function createEmptyMessage() {
  const message = document.createElement("p");
  message.className = "empty";
  message.textContent = "このカテゴリはまだ記事がありません。次回の自動更新後に表示されます。";
  return message;
}

function validateNews(data) {
  if (!data || !Array.isArray(data.categories)) {
    throw new Error("news.json の形式が正しくありません。categories 配列が必要です。");
  }
}

function setActiveTab(categoryId) {
  document.querySelectorAll(".tab-button").forEach((button) => {
    const selected = button.dataset.category === categoryId;
    button.classList.toggle("is-active", selected);
    button.setAttribute("aria-selected", String(selected));
  });
}

function renderCategory(categoryId) {
  if (!newsData) return;

  const category = newsData.categories.find((item) => normalizeCategoryId(item) === categoryId);
  if (!category) {
    throw new Error(`カテゴリ ${categoryId} が news.json に見つかりません。`);
  }

  activeCategoryId = categoryId;
  setActiveTab(categoryId);
  newsRoot.textContent = "";

  const panel = categoryTemplate.content.firstElementChild.cloneNode(true);
  panel.dataset.category = categoryId;
  panel.hidden = false;
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
}

function renderTabs(categories) {
  tabs.textContent = "";
  categories.forEach((category) => {
    const categoryId = normalizeCategoryId(category);
    const button = document.createElement("button");
    button.className = "tab-button";
    button.type = "button";
    button.dataset.category = categoryId;
    button.setAttribute("role", "tab");
    button.textContent = category.name;
    button.addEventListener("click", () => renderCategory(categoryId));
    tabs.append(button);
  });
}

function render(data) {
  validateNews(data);
  newsData = data;
  updatedEl.textContent = formatUpdatedAt(data.generatedAt);
  renderTabs(data.categories);

  const firstCategory = data.categories[0];
  const initialCategoryId = data.categories.some((category) => normalizeCategoryId(category) === activeCategoryId)
    ? activeCategoryId
    : normalizeCategoryId(firstCategory);

  renderCategory(initialCategoryId);
  statusEl.hidden = true;
}

async function loadNews() {
  try {
    const response = await fetch(NEWS_URL, { cache: "no-store" });
    if (!response.ok) {
      throw new Error(`${NEWS_URL} の取得に失敗しました。HTTP ${response.status}`);
    }
    const data = await response.json();
    render(data);
  } catch (error) {
    statusEl.hidden = false;
    statusEl.textContent = `ニュースを読み込めませんでした: ${error.message}`;
    updatedEl.textContent = "読み込み失敗";
    console.error(error);
  }
}

loadNews();
