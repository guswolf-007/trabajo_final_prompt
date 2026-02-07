// Tabs
//const API_URL = "/chat"; 
// ****************Para manejo de MARKDOWNS : ****************/
marked.setOptions({
  gfm: true,
  breaks: true,
  headerIds: false,
  mangle: false,
});
//******************************************************** */
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


function timeNow(){
  return new Date().toLocaleTimeString([], {hour:'2-digit', minute:'2-digit'});
}

function addUserMessage(text){
  const chat = document.getElementById("chat-messages");
  if (!chat) return;

  const row = document.createElement("div");
  row.className = "chat-msg user";

  const bubble = document.createElement("div");
  bubble.className = "chat-bubble";
  bubble.textContent = text;

  row.appendChild(bubble);
  chat.appendChild(row);
  chat.scrollTop = chat.scrollHeight;
}

function addBotMessage(initialText = ""){
  const chat = document.getElementById("chat-messages");
  if (!chat) return null;
   

  const row = document.createElement("div");
  row.className = "chat-msg bot";

  const bubble = document.createElement("div");
  bubble.className = "chat-bubble";
  bubble.textContent = initialText;

  row.appendChild(bubble);
  chat.appendChild(row);
  chat.scrollTop = chat.scrollHeight;

  // 👇 IMPORTANTE: devolvemos la burbuja para streaming
  return bubble;
}



// ************************** invocar /chat_stream con streaming ******************************

const form = document.getElementById("chat-form");
const input = document.getElementById("chat-input");
//const botEl = addBotMessage("") || { textContent: "" };
//const botEl = addBotMessage("");

const botEl = "" || { textContent: "" };


// session fija  ( temporal, esto despues lo vamos a cambiar)
//const SESSION_ID = "web-session-1";

// Generacion de SESSION_ID persistente . Con esto cada usuario tiene su propia sesión.
// Si el usuario recarga la página, el contexto se mantiene. no necesita login ni cookies.
// La sesion generada con la clase JS Crypto es de este tipo: 
// SESSION_ID: '0bcf40c0-84e1-4aa7-9299-d40a451e0e5d

let SESSION_ID = localStorage.getItem("session_id");

if (!SESSION_ID) {
  SESSION_ID = crypto.randomUUID();
  localStorage.setItem("session_id", SESSION_ID);
}


// ************************** invocar /chat_stream con streaming ******************************

if (form && input) {
  form.addEventListener("submit", async (e) => {
    e.preventDefault();

    const text = input.value.trim();
    if (!text) return;

    input.value = "";
    input.focus();

    // 1) pinta el mensaje del usuario
    addUserMessage(text);

    // 2) contenedor del bot (vacío) para ir escribiendo
    const botEl = addBotMessage("");
    botEl.innerHTML = `
     <span class="typing">
       <span></span><span></span><span></span>
     </span>`;

    try {
      const res = await fetch("/chat_stream", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          session_id: SESSION_ID,
          message: text,
          temperature: 0.7,
          max_output_tokens: 500
        })
      });

      if (!res.ok || !res.body) {
        const err = await res.text().catch(() => "");
        botEl.textContent = `❌ Error HTTP ${res.status} ${err}`;
        return;
      }

      const reader = res.body.getReader();
      const decoder = new TextDecoder("utf-8");
      let buffer = "";
      // ******* El siguiente cambio es para manejar los MARKDOWNS: ****
      let mdBuffer = "";
      //****************************************************************

      while (true) {
        const { value, done } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });

        // eventos SSE separados por línea en blanco
        const events = buffer.split("\n\n");
        buffer = events.pop();

        for (const evt of events) {
          const line = evt.trim();
          if (!line.startsWith("data:")) continue;

          const jsonStr = line.replace(/^data:\s*/, "");
          let msg;
          try {
            msg = JSON.parse(jsonStr);
          } catch {
            continue;
          }

          // ********NUevo codigo para manejo de MARKDOWNS ************
          if (msg.type === "chunk") {

            // elimina placeholder "typing" si existe
            if (botEl.querySelector(".typing")) {
              botEl.innerHTML = "";
            }

            // acumula markdown
            mdBuffer += msg.text;

            // renderiza markdown -> HTML
            mdBuffer = mdBuffer
                      .replace(/:\s*-\s*/g, ":\n- ")
                      .replace(/\s+-\s+\*\*/g, "\n- **");
            botEl.innerHTML = marked.parse(mdBuffer);

            // autoscroll
            const chat = document.getElementById("chat-messages");
            chat.scrollTop = chat.scrollHeight;

          } else if (msg.type === "error") {
            mdBuffer += `\n\n❌ **Error:** ${msg.message}`;
            botEl.innerHTML = marked.parse(mdBuffer);
          }
          //******************************************************* */

          
          /****** 
          if (msg.type === "chunk") {
             if (botEl.querySelector(".typing")){
              botEl.textContent = ""; 
             }
            
            botEl.textContent += msg.text;

            // autoscroll suave
            const chat = document.getElementById("chat-messages"); 
            chat.scrollTop =chat.scrollHeight;

            //botEl.scrollIntoView({ behavior: "smooth", block: "end" });  
          } else if (msg.type === "error") {
            botEl.textContent += `\n❌ ${msg.message}`;
          } else if (msg.type === "done") {
            // opcional: algo visual al terminar
          }
          *********/ 
        }
      }
    } catch (err) {
      botEl.textContent = `❌ ${err?.message || String(err)}`;
    }
  });
} else {
  console.warn("No se encontró #chat-form o #chat-input. Revisa IDs en index.html.");
}



form?.addEventListener("submit", () => {
  console.log("submit detectado ✅");
});

window.addEventListener("load", () => {
  addBotMessage("¡Hola! 👋 Soy tu asistente bancario. ¿En qué te ayudo hoy?");
});


console.log("app.js cargado OK");
