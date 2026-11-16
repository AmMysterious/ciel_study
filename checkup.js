/* Ciel Study - the free check-up bar (16 Nov 2026, every page).
   A slim bar fixed to the bottom of the screen pointing at the bot's free 10-question
   day-one check-up. NOT a popup: it covers nothing in the middle of the page.
   Fixed, so it never moves the page; the body gets bottom room only so the footer
   is not hidden under it. The x hides it for good on this browser (localStorage,
   try/catch: private windows throw). Without JS the bar simply is not there - the
   home page still carries the same line in plain HTML under its main button. */
(function () {
  var KEY = 'ciel_checkup_bar_closed';
  try { if (localStorage.getItem(KEY)) return; } catch (e) {}

  var bar = document.createElement('aside');
  bar.className = 'checkup-bar';
  bar.setAttribute('aria-label', 'Free check-up');
  bar.innerHTML =
    '<a class="checkup-link" href="https://t.me/Ciel_Study_bot?start=site_checkup">' +
      '<span aria-hidden="true">🩺</span> <span><b>Free 10-question check-up</b> — see your strong and weak subjects' +
      ' <span class="checkup-go">· Start in Telegram →</span></span></a>' +
    '<button type="button" class="checkup-x" aria-label="Hide the check-up bar">×</button>';

  bar.querySelector('.checkup-x').addEventListener('click', function () {
    bar.remove();
    document.documentElement.classList.remove('has-checkup');
    try { localStorage.setItem(KEY, '1'); } catch (e) {}
  });

  document.body.appendChild(bar);
  document.documentElement.classList.add('has-checkup');
})();
