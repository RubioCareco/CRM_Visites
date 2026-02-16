(function(){
  function $(id){ return document.getElementById(id); }

  function render(){
    var list = $("dbtSelectedList");
    var count = $("dbtSelCount");
    if(!list || !count) return;

    var set = window.dbtSelectedClientIds || new Set();
    var ids = Array.from(set);

    count.textContent = String(ids.length);
    list.innerHTML = "";

    if(ids.length === 0){
      var empty = document.createElement("div");
      empty.style.color = "#64748b";
      empty.style.fontSize = "12px";
      empty.textContent = "Clique sur des clients sur la carte pour les ajouter ici.";
      list.appendChild(empty);
      return;
    }

    ids.forEach(function(id){
      var row = document.createElement("div");
      row.style.display = "flex";
      row.style.alignItems = "center";
      row.style.justifyContent = "space-between";
      row.style.gap = "10px";
      row.style.padding = "10px";
      row.style.border = "1px solid #e5e7eb";
      row.style.borderRadius = "12px";
      row.style.background = "#fff";

      var left = document.createElement("div");
      left.style.fontWeight = "800";
      left.style.fontSize = "13px";
      left.style.wordBreak = "break-word";
      var c = (window.dbtClientsById && window.dbtClientsById[Number(id)]) || null;
      var name = (c && (c.rs_nom || c.nom || c.name)) ? (c.rs_nom || c.nom || c.name) : ("Client #" + id);

      left.innerHTML = "";
      left.style.fontWeight = "normal";
      left.style.fontSize = "13px";
      left.style.wordBreak = "break-word";

      var t = document.createElement("div");
      t.textContent = name;
      t.style.fontWeight = "800";
      t.style.fontSize = "13px";
      t.style.wordBreak = "break-word";
      left.appendChild(t);

      // Sous-ligne: CP + ville + adresse si dispo
      var cp = (c && (c.code_postal || c.cp)) ? (c.code_postal || c.cp) : "";
      var ville = (c && (c.ville || c.city)) ? (c.ville || c.city) : "";
      var adr = (c && (c.adresse || c.address || c.adresse_complete)) ? (c.adresse || c.address || c.adresse_complete) : "";

      var subParts = [];
      var cpVille = (cp || ville) ? ((cp ? cp : "") + (cp && ville ? " " : "") + (ville ? ville : "")) : "";
      if (cpVille) subParts.push(cpVille);
      if (adr) subParts.push(adr);

      if (subParts.length){
        var st = document.createElement("div");
        st.textContent = subParts.join(" • ");
        st.style.marginTop = "4px";
        st.style.fontSize = "12px";
        st.style.color = "#64748b";
        st.style.wordBreak = "break-word";
        left.appendChild(st);
      }
      var btn = document.createElement("button");
      btn.type = "button";
      btn.textContent = "Retirer";
      btn.style.padding = "6px 10px";
      btn.style.borderRadius = "10px";
      btn.style.border = "1px solid #e5e7eb";
      btn.style.background = "#fff";
      btn.style.cursor = "pointer";
      btn.style.fontSize = "12px";

      btn.addEventListener("click", function(ev){
        ev.preventDefault(); ev.stopPropagation();
        if (typeof window.dbtToggleSelected === "function") window.dbtToggleSelected(Number(id));
        render();
      });

      row.appendChild(left);
      row.appendChild(btn);
      list.appendChild(row);
    });
  }

  // Hook "Vider"
  document.addEventListener("click", function(e){
    if(e && e.target && e.target.id === "dbtSelClear"){
      var ids = Array.from(window.dbtSelectedClientIds || []);
      if (typeof window.dbtToggleSelected === "function"){
        ids.forEach(function(id){ window.dbtToggleSelected(Number(id)); });
      } else {
        window.dbtSelectedClientIds = new Set(); // fallback
      }
      render();
    }
  }, true);

  // Expose helper (utile)
  window.dbtRenderSelectedSidebar = render;

  // Render au chargement (si déjà des selections)
  document.addEventListener("DOMContentLoaded", function(){
    try{ render(); }catch(e){}
  });
})();
