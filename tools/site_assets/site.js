// Index page search + tag filter — operates entirely on the DOM and the
// small prebuilt window.__COURSES__ blob, no network requests at all.
(function () {
  var searchInput = document.getElementById('search');
  var grid = document.getElementById('course-grid');
  var noResults = document.getElementById('no-results');
  var tagButtons = document.querySelectorAll('.tag-filter');
  if (!grid) return;

  var cards = Array.prototype.slice.call(grid.querySelectorAll('.course-card'));
  var activeTag = '';

  function applyFilter() {
    var query = (searchInput.value || '').trim().toLowerCase();
    var visibleCount = 0;
    cards.forEach(function (card) {
      var matchesTag = !activeTag || (card.dataset.tags || '').split(' ').indexOf(activeTag) !== -1;
      var haystack = card.dataset.title + ' ' + card.dataset.desc + ' ' + card.dataset.tags;
      var matchesQuery = !query || haystack.indexOf(query) !== -1;
      var visible = matchesTag && matchesQuery;
      card.hidden = !visible;
      if (visible) visibleCount += 1;
    });
    noResults.hidden = visibleCount !== 0;
  }

  searchInput.addEventListener('input', applyFilter);
  tagButtons.forEach(function (btn) {
    btn.addEventListener('click', function () {
      activeTag = btn.dataset.tag || '';
      tagButtons.forEach(function (b) { b.classList.toggle('active', b === btn); });
      applyFilter();
    });
  });
})();
