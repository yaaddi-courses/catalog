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
  var sentinel = document.getElementById('load-sentinel');
  var tagButtons = document.querySelectorAll('.tag-filter');
  if (!grid) return;

  var allCourses = window.__COURSES__ || [];
  var activeTag = '';
  var filtered = allCourses; // recomputed on search/tag change
  var renderedCount = grid.querySelectorAll('.course-card').length; // server-rendered batch already in the DOM
  var filtering = false; // true once the user has searched/filtered at least once

  function courseMatches(course, query, tag) {
    if (tag && (course.tags || []).indexOf(tag) === -1) return false;
    if (!query) return true;
    var haystack = (course.title + ' ' + course.description + ' ' + (course.tags || []).join(' ')).toLowerCase();
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
    h3.textContent = course.title;
    body.appendChild(h3);

    var desc = document.createElement('p');
    desc.className = 'course-desc';
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
    decks.textContent = course.deckCount + ' decks';
    var dot = document.createElement('span');
    dot.textContent = '·';
    var cards = document.createElement('span');
    cards.textContent = course.cardCount + ' cards';
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

  function applyFilter() {
    var query = (searchInput.value || '').trim().toLowerCase();
    filtering = true;
    filtered = allCourses.filter(function (c) {
      return courseMatches(c, query, activeTag);
    });
    grid.innerHTML = '';
    renderedCount = 0;
    renderNextBatch();
    noResults.hidden = filtered.length !== 0;
  }

  searchInput.addEventListener('input', applyFilter);
  tagButtons.forEach(function (btn) {
    btn.addEventListener('click', function () {
      activeTag = btn.dataset.tag || '';
      tagButtons.forEach(function (b) { b.classList.toggle('active', b === btn); });
      applyFilter();
    });
  });

  // Not filtering yet: the server-rendered first batch is already in the
  // DOM, so `filtered` (still the full unfiltered list) just needs more of
  // itself appended as the sentinel comes into view.
  if (sentinel && 'IntersectionObserver' in window) {
    var observer = new IntersectionObserver(function (entries) {
      if (entries.some(function (e) { return e.isIntersecting; })) {
        renderNextBatch();
      }
    });
    observer.observe(sentinel);
  } else if (sentinel) {
    // No IntersectionObserver support (very old browser) — fall back to
    // rendering everything up front rather than leaving the rest
    // permanently unreachable.
    while (renderedCount < filtered.length) renderNextBatch();
  }
})();
