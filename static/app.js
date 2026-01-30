// Tabs
const tabs = document.querySelectorAll('.tab');
const panels = {
  cards: document.getElementById('panel-cards'),
  discounts: document.getElementById('panel-discounts'),
  benefits: document.getElementById('panel-benefits'),
};

tabs.forEach((t) => {
  t.addEventListener('click', () => {
    tabs.forEach(x => x.classList.remove('is-active'));
    t.classList.add('is-active');

    const key = t.dataset.tab;
    Object.entries(panels).forEach(([k, el]) => {
      const isOn = (k === key);
      el.hidden = !isOn;
      el.classList.toggle('is-active', isOn);
    });
  });
});

// Bank selection toggles (purely visual, but also hides comparison columns)
const bankCards = document.querySelectorAll('.bank');
const selected = new Set(['bchile','falabella','santander','bci']);

function syncTable(){
  document.querySelectorAll('.cell').forEach((cell) => {
    const bank = cell.dataset.for;
    cell.style.display = selected.has(bank) ? '' : 'none';
  });
  // headers
  const map = {
    bchile: '.th--bchile',
    falabella: '.th--falabella',
    santander: '.th--santander',
    bci: '.th--bci',
  };
  Object.entries(map).forEach(([bank, selector]) => {
    const th = document.querySelector(selector);
    if (th) th.style.display = selected.has(bank) ? '' : 'none';
  });
}

function toggleBank(card){
  const bank = card.dataset.bank;
  const on = selected.has(bank);

  if (on && selected.size === 1) {
    // keep at least one selected
    return;
  }

  if (on) selected.delete(bank);
  else selected.add(bank);

  card.classList.toggle('is-off', !selected.has(bank));
  card.setAttribute('aria-pressed', String(selected.has(bank)));

  const pill = card.querySelector('.pill');
  if (pill) pill.style.opacity = selected.has(bank) ? '1' : '.35';

  syncTable();
}

bankCards.forEach((card) => {
  card.addEventListener('click', () => toggleBank(card));
  card.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' || e.key === ' ') {
      e.preventDefault();
      toggleBank(card);
    }
  });
});

// Buttons (scroll helpers)
document.getElementById('btnCompare')?.addEventListener('click', () => {
  document.getElementById('comparacion')?.scrollIntoView({behavior:'smooth', block:'start'});
});
document.getElementById('btnAsk')?.addEventListener('click', () => {
  document.getElementById('dudas')?.scrollIntoView({behavior:'smooth', block:'start'});
});

syncTable();
