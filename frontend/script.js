const API = "https://TON_BACKEND_URL.onrender.com";
const form = document.getElementById("form");
form.onsubmit = async (e) => {
 e.preventDefault();
 const data = new FormData(form);
 const res = await fetch(API + "/upload", {method: "POST", body: data});
 const results = await res.json();
 const container = document.getElementById("results");
 container.innerHTML = "";
 results.forEach(r => {
  let html = `<h3>${r.input}</h3>`;
  if (r.matches.length === 0) {
    html += `<button onclick="create('${r.input}')">Créer</button>`;
  } else {
    r.matches.forEach(m => {
      html += `<div>${m.name} (${m.score}%) <button onclick="update('${m.id}')">Valider</button></div>`;
    });
  }
  const div = document.createElement('div');
  div.innerHTML = html;
  container.appendChild(div);
 });
};
async function update(id){
 const status = document.querySelector("select").value;
 await fetch(API + "/validate", {method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify({action:"update",record_id:id,status:status})});
 alert("✅ mis à jour");
}
async function create(name){
 const status = document.querySelector("select").value;
 await fetch(API + "/validate", {method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify({action:"create",name:name,status:status})});
 alert("✅ créé");
}
