RegExp.escape = function escape(text) {
  if (!arguments.callee.sRE) {
    var specials = [
      '.', '*', '+', '?', '|', '(', ')', '[', ']', '{', '}', '\\', '$', '^'
    ];
    arguments.callee.sRE = new RegExp(
      '(\\' + specials.join('|\\') + ')', 'g'
    );
  }
  return text.replace(arguments.callee.sRE, '\\$1');
}

String.prototype.HalfHTMLEscape = function() {
    return this.replace(/&/g, '&amp;').replace(/>/g, '&gt;').replace(/</g, '&lt;');
}

String.prototype.HTMLEscape = function HTMLEscape() {
    return this.HalfHTMLEscape().replace(/"/g, '&quot;').replace(/'/g, '&#39;');
}

var banlog = {
    doneSetup: false,
    hform: null,
    log_id: null,
    mark: null,
    regex: null,
    textlog: null,
    lines: null,
    force: false,

    log: function() {},

    highlight: function() {
        var term = banlog.mark.value;

        banlog.log("term: " + term + "\nbanlog.regex.checked: " + banlog.regex.checked)

        if(term == "") {
            for(var i=0; i<banlog.lines.length; ++i)
                banlog.lines[i].className = "";
            return true;
        }

        try {
            if(banlog.regex.checked) {
                banlog.log("term: " + term.HalfHTMLEscape());
                term = new RegExp(term.HalfHTMLEscape(), 'i')
            } else {
                banlog.log("term: " + RegExp.escape(term.HTMLEscape()));
                term = new RegExp(RegExp.escape(term.HTMLEscape()), 'i')
            }
        } catch(err) {
            banlog.log(err);
            return true;
        }

        for(var i=0; i<banlog.lines.length; ++i) {
            var line = banlog.lines[i];
            if(term.test(line.innerHTML)) {
                line.className = "highlight"
            } else {
                line.className = ""
            }
        }
        return true;
    },

    keyup: function() {
        banlog.highlight();
    },

    submit: function(e) {
        if(banlog.force)
            return true;
        banlog.highlight();
        e.preventDefault();
        return false;
    },

    dolog: function() {
        banlog.log("this: " + this + ", arguments:" + arguments[0]);
        return false;
    },

    setup: function() {
        if(banlog.doneSetup) return;
        banlog.doneSetup = true;
//        if(window.console && console.log)
//            banlog.log = console.log;

        banlog.hform = document.getElementById("hform");
        banlog.log_id = document.getElementById("log").value;
        banlog.mark = document.getElementById("mark");
        banlog.regex = document.getElementById("regex");
        banlog.textlog = document.getElementById("textlog");
        banlog.lines = banlog.textlog.getElementsByTagName("span");

        banlog.hform.addEventListener("submit", banlog.submit , false);
        banlog.mark.addEventListener("keyup", banlog.keyup , false);
        banlog.regex.addEventListener("change", banlog.keyup , false);

        var really_submit = document.createElement("input");
        really_submit.type = 'submit';
        really_submit.className = 'input';
        really_submit.value = 'Refresh';
        really_submit.addEventListener('click', function() { banlog.force = true; }, false);
        banlog.hform.appendChild(really_submit);
    }
};

if(window.addEventListener) {
    window.addEventListener('load', banlog.setup, false);
} else if(document.addEventListener) {
    document.addEventListener('load', banlog.setup, false);
} else {
    window.onload = document.onload = banlog.setup;
}

