// Index page search + tag filter + infinite scroll.
//
// Scaling note: a catalog of thousands of courses can't have every card's
// markup sitting in the DOM at once (thousands of nodes, most never seen)
// or shipped as one giant index.html. build_site.py now renders only the
// first PAGE_SIZE cards directly into the page (fast first paint, and a
// working page with JS disabled — those are real links). Everything else
// lives in the small `window.__COURSES__` data blob and is rendered here,
// in batches, as the user actually scrolls near the bottom — never the
// whole remaining catalog at once, however large it is. Searching/filtering
// re-runs against the *full* `window.__COURSES__` list (not just whatever
// happens to be in the DOM already), so a match beyond the first
// server-rendered batch is still found — but still renders progressively,
// the same way, so a search matching thousands of courses doesn't dump
// thousands of DOM nodes in one go either.
(function () {
  var PAGE_SIZE = 60;

  var searchInput = document.getElementById('search');
  var grid = document.getElementById('course-grid');
  var noResults = document.getElementById('no-results');
  var resultsStatus = document.getElementById('results-status');
  var sentinel = document.getElementById('load-sentinel');
  var tagButtons = document.querySelectorAll('.tag-filter');
  if (!grid) return;

  var allCourses = window.__COURSES__ || [];
  var activeTag = '';
  var filtered = allCourses; // recomputed on search/tag change
  var renderedCount = grid.querySelectorAll('.course-card').length; // server-rendered batch already in the DOM
  var filtering = false; // true once the user has searched/filtered at least once

  function plural(n, word) {
    return n + ' ' + (n === 1 ? word : word + 's');
  }

  // Search text folding: lower case, Arabic yeh/kaf typed on some keyboards matched to the
  // Persian letters (ي→ی, ى→ی, ك→ک), and Persian/Arabic-Indic digits matched to 0-9.
  function normalize(text) {
    return String(text || '')
      .toLowerCase()
      .replace(/[يى]/g, 'ی')
      .replace(/ك/g, 'ک')
      .replace(/[۰-۹]/g, function (d) { return String(d.charCodeAt(0) - 0x06F0); })
      .replace(/[٠-٩]/g, function (d) { return String(d.charCodeAt(0) - 0x0660); });
  }

  function courseMatches(course, query, tag) {
    if (tag && (course.tags || []).indexOf(tag) === -1) return false;
    if (!query) return true;
    var haystack = normalize(course.title + ' ' + course.description + ' ' + (course.tags || []).join(' '));
    return haystack.indexOf(query) !== -1;
  }

  function createCardElement(course) {
    var a = document.createElement('a');
    a.className = 'course-card';
    a.href = 'courses/' + course.slug + '/index.html';

    if (course.image) {
      var img = document.createElement('img');
      img.className = 'cover';
      img.src = course.image;
      img.alt = '';
      img.loading = 'lazy';
      a.appendChild(img);
    } else {
      var emptyCover = document.createElement('div');
      emptyCover.className = 'cover cover-empty';
      a.appendChild(emptyCover);
    }

    var body = document.createElement('div');
    body.className = 'course-card-body';

    var h3 = document.createElement('h3');
    h3.dir = 'auto'; // a Farsi title reads right-to-left (same as build_site.py)
    h3.textContent = course.title;
    body.appendChild(h3);

    var desc = document.createElement('p');
    desc.className = 'course-desc';
    desc.dir = 'auto';
    desc.textContent = course.description;
    body.appendChild(desc);

    var tagRow = document.createElement('div');
    tagRow.className = 'tag-row';
    (course.tags || []).forEach(function (t) {
      var chip = document.createElement('span');
      chip.className = 'chip';
      chip.textContent = t;
      tagRow.appendChild(chip);
    });
    body.appendChild(tagRow);

    var stats = document.createElement('div');
    stats.className = 'course-stats';
    var decks = document.createElement('span');
    decks.textContent = plural(course.deckCount, 'deck');
    var dot = document.createElement('span');
    dot.textContent = '·';
    var cards = document.createElement('span');
    cards.textContent = plural(course.cardCount, 'card');
    stats.appendChild(decks);
    stats.appendChild(dot);
    stats.appendChild(cards);
    body.appendChild(stats);

    a.appendChild(body);
    return a;
  }

  function renderNextBatch() {
    if (renderedCount >= filtered.length) return;
    var batch = filtered.slice(renderedCount, renderedCount + PAGE_SIZE);
    var fragment = document.createDocumentFragment();
    batch.forEach(function (course) {
      fragment.appendChild(createCardElement(course));
    });
    grid.appendChild(fragment);
    renderedCount += batch.length;
  }

  // IntersectionObserver only fires when visibility CHANGES: if the sentinel is still on
  // screen after a batch (tall window, short cards), keep adding batches until it is not.
  function sentinelVisible() {
    return sentinel && sentinel.getBoundingClientRect().top <= window.innerHeight;
  }

  function fillWhileVisible() {
    renderNextBatch();
    while (renderedCount < filtered.length && sentinelVisible()) renderNextBatch();
  }

  // Search text and tag live in the URL hash (#q=...&tag=...), so going back from a
  // course page returns to the same filtered list.
  function saveState(query) {
    var parts = [];
    if (query) parts.push('q=' + encodeURIComponent(query));
    if (activeTag) parts.push('tag=' + encodeURIComponent(activeTag));
    var hash = parts.length ? '#' + parts.join('&') : '';
    if (window.history && history.replaceState) {
      history.replaceState(null, '', hash || window.location.pathname + window.location.search);
    }
  }

  function setActiveTag(tag) {
    activeTag = tag;
    tagButtons.forEach(function (b) {
      var on = (b.dataset.tag || '') === tag;
      b.classList.toggle('active', on);
      b.setAttribute('aria-pressed', on ? 'true' : 'false');
    });
  }

  function applyFilter() {
    var raw = (searchInput.value || '').trim();
    var query = normalize(raw);
    filtering = true;
    filtered = allCourses.filter(function (c) {
      return courseMatches(c, query, activeTag);
    });
    grid.innerHTML = '';
    renderedCount = 0;
    fillWhileVisible();
    noResults.hidden = filtered.length !== 0;
    saveState(raw);
    // Screen readers hear the result of a search/filter (role="status" live region).
    if (resultsStatus) {
      resultsStatus.textContent = filtered.length === 0
        ? 'No courses match your search.'
        : plural(filtered.length, 'course') + ' found';
    }
  }

  searchInput.addEventListener('input', applyFilter);
  tagButtons.forEach(function (btn) {
    btn.addEventListener('click', function () {
      setActiveTag(btn.dataset.tag || '');
      applyFilter();
    });
  });

  // Not filtering yet: the server-rendered first batch is already in the
  // DOM, so `filtered` (still the full unfiltered list) just needs more of
  // itself appended as the sentinel comes into view.
  if (sentinel && 'IntersectionObserver' in window) {
    var observer = new IntersectionObserver(function (entries) {
      if (entries.some(function (e) { return e.isIntersecting; })) {
        fillWhileVisible();
      }
    });
    observer.observe(sentinel);
  } else if (sentinel) {
    // No IntersectionObserver support (very old browser) — fall back to
    // rendering everything up front rather than leaving the rest
    // permanently unreachable.
    while (renderedCount < filtered.length) renderNextBatch();
  }

  // Restore a search/tag kept in the URL hash (e.g. after "back" from a course page).
  var params = {};
  window.location.hash.replace(/^#/, '').split('&').forEach(function (pair) {
    var i = pair.indexOf('=');
    if (i > 0) {
      try { params[pair.slice(0, i)] = decodeURIComponent(pair.slice(i + 1)); } catch (e) { /* malformed hash: ignore */ }
    }
  });
  if (params.q || params.tag) {
    searchInput.value = params.q || '';
    var known = Array.prototype.some.call(tagButtons, function (b) { return (b.dataset.tag || '') === params.tag; });
    setActiveTag(known ? params.tag : '');
    applyFilter();
  }
})();
