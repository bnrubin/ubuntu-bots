window.addEventListener("load", function() {
    sc = document.createElement("script");
    sc.setAttribute("type", "text/javascript");
    sc.setAttribute("src", "banlog.js");
    document.getElementsByTagName("head")[0].appendChild(sc);
}, false);

s = null;
r = null;

function getObj(name) {
  if (document.getElementById) {
    this.obj = document.getElementById(name);
    this.style = document.getElementById(name).style;
  }
  else if (document.all) {
    this.obj = document.all[name];
    this.style = document.all[name].style;
  }
  else if (document.layers) {
    this.obj = document.layers[name];
    this.style = document.layers[name];
  }
}

function toggle(item,prefix) {
  var c  = new getObj(prefix + '_' + item);
  if ( c.style.display == 'inline' ) {
    c.style.display = 'none';
  } else {
    c.style.display = 'inline';
  }
}

function showlog(item) {
  if (s == item) {
        c = new getObj('log');
        if( c.style.display == 'block' || c.style.display == '' ) {
            c.style.display = 'none';
            document.getElementById("loglink-" + item).textContent = "inline";
        } else {
            c.style.diaply = 'block';
            document.getElementById("loglink-" + item).textContent = "Hide";
        }
    s = null;
  } else {
    loadlog(item);
  }
}

function loadlog(id) {
  r = new XMLHttpRequest();
  var qobj = new getObj("query");
/*
  var objv = [];
  for(var i in qobj)
    objv.push(i);
  alert(objv);
*/
  var reqUri = "bans.cgi?log=" + id;
  if(qobj.obj.value && qobj.obj.value != '')
    reqUri += "&mark=" + qobj.obj.value.split(' ').pop();
  reqUri += "&plain=1";
  r.onreadystatechange = printlog;
  r.open("GET", reqUri, true);
  r.send(null);
  s = id;
}

function printlog() {
  if (r.readyState == 4) {
    var c = new getObj('log');
    c.obj.innerHTML = r.responseText;
    document.getElementById("loglink-" + s).textContent = "Hide";
    c.style.display = 'block';
    setupHighlight();
  }
}
