(function(){
var norm=function(s){return(s||"").toLowerCase().normalize("NFD").replace(/[\u0300-\u036f]/g,"")};
var dlg=document.getElementById("dlg-grafico");
if(dlg){document.addEventListener("click",function(e){
  var b=e.target.closest("[data-chart]");
  if(b){var im=dlg.querySelector("img");im.src=b.dataset.chart;im.alt="Histórico de preços: "+b.dataset.title;
    dlg.querySelector("h3").textContent=b.dataset.title;dlg.showModal();return}
  if(e.target.closest("[data-fechar]")||e.target===dlg)dlg.close()})}
var raiz=document.querySelector("[data-filtravel]");if(!raiz)return;
var lista=raiz.querySelector("[data-lista]"),itens=[].slice.call(lista.children);
var busca=raiz.querySelector("[data-busca]"),ordem=raiz.querySelector("[data-ordem]"),
    mais=raiz.querySelector("[data-mais]"),cont=raiz.querySelector("[data-contagem]"),
    vazio=raiz.querySelector("[data-vazio]"),barra=raiz.querySelector("[data-barra]");
var passo=parseInt(raiz.dataset.passo||"24",10),st={q:"",f:"todos",n:passo};
var num=function(el,k){return parseFloat(el.dataset[k])||0};
var ord={desconto:function(a,b){return num(b,"off")-num(a,"off")||num(a,"i")-num(b,"i")},
  "preco-asc":function(a,b){return num(a,"price")-num(b,"price")},
  "preco-desc":function(a,b){return num(b,"price")-num(a,"price")},
  az:function(a,b){return a.dataset.nome<b.dataset.nome?-1:1},
  recentes:function(a,b){return num(a,"i")-num(b,"i")}};
function aplicar(){
  var f=itens.filter(function(el){
    if(st.q&&el.dataset.nome.indexOf(st.q)<0)return false;
    if(st.f==="promo")return num(el,"off")>0;
    if(st.f==="low")return el.dataset.low==="1";
    if(st.f.indexOf("cat:")===0)return el.dataset.cat===st.f.slice(4);
    return true});
  f.sort(ord[ordem?ordem.value:"recentes"]||ord.recentes);
  itens.forEach(function(el){el.hidden=true});
  f.forEach(function(el,i){lista.appendChild(el);el.hidden=i>=st.n});
  var vis=Math.min(st.n,f.length);
  if(cont)cont.textContent=f.length?("Mostrando "+vis+" de "+f.length):"";
  if(mais)mais.hidden=vis>=f.length;
  if(vazio)vazio.hidden=f.length>0}
if(barra)barra.hidden=false;
var t;if(busca)busca.addEventListener("input",function(){clearTimeout(t);t=setTimeout(function(){
  st.q=norm(busca.value.trim());st.n=passo;aplicar()},120)});
if(ordem)ordem.addEventListener("change",function(){st.n=passo;aplicar()});
raiz.addEventListener("click",function(e){
  var c=e.target.closest(".chip");
  if(c){raiz.querySelectorAll(".chip").forEach(function(x){x.setAttribute("aria-pressed",x===c)});
    st.f=c.dataset.f;st.n=passo;aplicar()}
  if(e.target.closest("[data-mais]")){st.n+=passo;aplicar()}});
aplicar()})();
