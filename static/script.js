function copyText(id){
 const el=document.getElementById(id);
 if(!el) return;
 navigator.clipboard.writeText(el.value||el.innerText);
 alert("Copied!");
}
function confirmDelete(){
 return confirm("Delete this URL?");
}
