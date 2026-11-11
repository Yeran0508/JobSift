const state = { cursor: null, loading: false, selectedLocations: new Set(), selectedSkills: new Set(), jobs: new Map() };
const byId = (id) => document.getElementById(id);
const form = byId("search-form");
const results = byId("results");

function setPanel(name) {
  ["loading", "empty", "error"].forEach((item) => { byId(`state-${item}`).hidden = item !== name; });
}

function params(cursor = null) {
  const query = new URLSearchParams();
  const text = byId("query").value.trim();
  if (text) query.set("q", text);
  state.selectedLocations.forEach((value) => query.append("location", value));
  state.selectedSkills.forEach((value) => query.append("skill", value));
  if (byId("posted-from").value) query.set("posted_from", `${byId("posted-from").value}T00:00:00Z`);
  query.set("size", "10");
  if (cursor) query.set("cursor", cursor);
  return query;
}

async function search({ append = false } = {}) {
  if (state.loading) return;
  state.loading = true;
  if (!append) { results.replaceChildren(); setPanel("loading"); }
  byId("load-more").hidden = true;
  byId("partial-banner").hidden = true;
  try {
    const response = await fetch(`/api/v1/jobs?${params(append ? state.cursor : null)}`, { headers: { Accept: "application/json" } });
    const payload = await response.json();
    if (!response.ok) throw new Error(payload.detail?.message || "The search service could not respond.");
    state.cursor = payload.next_cursor;
    payload.results.forEach((job) => { state.jobs.set(job.id, job); results.append(renderJob(job)); });
    renderFacets("location-facets", payload.facets.locations, state.selectedLocations, "location");
    renderFacets("skill-facets", payload.facets.skills, state.selectedSkills, "skill");
    byId("result-count").textContent = `${payload.total.toLocaleString()} ${payload.total === 1 ? "role" : "roles"}`;
    byId("search-time").textContent = `${payload.meta.took_ms} ms · indexed snapshot`;
    if (payload.meta.is_partial) {
      byId("partial-banner").textContent = payload.meta.warnings.join(" ");
      byId("partial-banner").hidden = false;
    }
    setPanel(payload.total === 0 ? "empty" : null);
    byId("load-more").hidden = !state.cursor;
  } catch (error) {
    if (!append) results.replaceChildren();
    byId("error-message").textContent = error.message;
    setPanel("error");
    byId("result-count").textContent = "Search interrupted";
    byId("search-time").textContent = "";
  } finally { state.loading = false; }
}

function renderJob(job) {
  const article = document.createElement("article");
  article.className = "job-card";
  const posted = job.posted_at ? new Date(job.posted_at).toLocaleDateString(undefined, { month: "short", day: "numeric" }) : "Date unknown";
  const indexed = new Date(job.acquired_at).toLocaleDateString(undefined, { month: "short", day: "numeric" });
  article.innerHTML = `<div><h3><button type="button" data-detail="${job.id}">${escapeHtml(job.title)}</button></h3><div class="company-line"><strong>${escapeHtml(job.company)}</strong><span>${escapeHtml(job.location || "Location not listed")}</span><span>${escapeHtml(job.employment_type || "Type not listed")}</span></div><div class="tags">${job.skills.slice(0, 5).map((skill) => `<span class="tag">${escapeHtml(skill)}</span>`).join("")}</div></div><div class="job-side"><time>Posted ${posted}</time><span class="source-label">${escapeHtml(job.source)}</span><small>Indexed ${indexed}</small></div>`;
  article.querySelector("button").addEventListener("click", () => showDetail(job));
  return article;
}

function renderFacets(containerId, facets, selected, paramName) {
  const container = byId(containerId);
  const keys = new Set(facets.map((facet) => facet.key));
  selected.forEach((key) => { if (!keys.has(key)) facets.push({ key, count: 0 }); });
  if (!facets.length) { container.innerHTML = '<span class="muted">No facets in this result</span>'; return; }
  container.replaceChildren(...facets.slice(0, 10).map((facet) => {
    const label = document.createElement("label"); label.className = "facet";
    const input = document.createElement("input"); input.type = "checkbox"; input.checked = selected.has(facet.key);
    input.addEventListener("change", () => { input.checked ? selected.add(facet.key) : selected.delete(facet.key); search(); });
    const name = document.createElement("span"); name.textContent = facet.key;
    const count = document.createElement("span"); count.textContent = facet.count;
    label.append(input, name, count); label.dataset.param = paramName; return label;
  }));
}

function showDetail(job) {
  const salary = job.salary_min == null ? "Salary not listed" : `${job.salary_currency || ""} ${Math.round(job.salary_min).toLocaleString()}${job.salary_max ? `–${Math.round(job.salary_max).toLocaleString()}` : ""} ${job.salary_period || ""}`.trim();
  byId("detail-content").innerHTML = `<p class="detail-eyebrow">${escapeHtml(job.source)} · public listing</p><h2 id="detail-title">${escapeHtml(job.title)}</h2><p class="detail-meta">${escapeHtml(job.company)} · ${escapeHtml(job.location || "Location not listed")}</p><div class="tags">${job.skills.map((skill) => `<span class="tag">${escapeHtml(skill)}</span>`).join("")}</div><p class="detail-description">${escapeHtml(job.description || "No description was provided by the source.")}</p><p><strong>${escapeHtml(salary)}</strong></p><a class="source-link" href="${escapeAttribute(job.url)}" target="_blank" rel="noopener noreferrer">View original source ↗</a>`;
  byId("job-detail").showModal();
}

function escapeHtml(value) { const node = document.createElement("div"); node.textContent = String(value); return node.innerHTML; }
function escapeAttribute(value) { return String(value).replaceAll("&", "&amp;").replaceAll('"', "&quot;").replaceAll("<", "&lt;"); }

form.addEventListener("submit", (event) => { event.preventDefault(); search(); });
document.querySelectorAll("[data-query]").forEach((button) => button.addEventListener("click", () => { byId("query").value = button.dataset.query; search(); }));
byId("posted-from").addEventListener("change", () => search());
byId("clear-filters").addEventListener("click", () => { state.selectedLocations.clear(); state.selectedSkills.clear(); byId("posted-from").value = ""; search(); });
byId("retry-search").addEventListener("click", () => search());
byId("load-more").addEventListener("click", () => search({ append: true }));
byId("close-detail").addEventListener("click", () => byId("job-detail").close());
byId("job-detail").addEventListener("click", (event) => { if (event.target === byId("job-detail")) byId("job-detail").close(); });
search();
