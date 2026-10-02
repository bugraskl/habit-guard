// Habit Guard website. Progressive enhancement only: without JavaScript every link still works
// and the demo shows its zones. No analytics, no cookies, no storage, no requests to other sites.
(function () {
  "use strict";

  var header = document.querySelector(".topbar");
  function onScroll() {
    if (header) header.classList.toggle("scrolled", window.scrollY > 8);
  }
  window.addEventListener("scroll", onScroll, { passive: true });
  onScroll();

  document.querySelectorAll("[data-demo]").forEach(demo);

  // The hero demo: a face with the real zones, and a hand that goes to each of them in turn. A
  // fingertip in a zone fills a ring (the dwell time); when it is full the alarm goes off (the
  // frame turns red, a message appears); then the hand comes down and the alarm is released.
  // The visitor can take over by choosing a habit. Nothing here uses the camera.
  function demo(figure) {
    var hand = figure.querySelector(".hand");
    var ring = figure.querySelector(".ring");
    var pill = figure.querySelector(".alarm-pill");
    var status = figure.querySelector("[data-status]");
    var chips = Array.prototype.slice.call(figure.querySelectorAll("[data-habit]"));
    var zones = {};
    figure.querySelectorAll(".zone").forEach(function (zone) {
      zones[zone.getAttribute("data-habit")] = zone;
    });
    var reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)");

    var REST = [470, 560];
    var DWELL = { nail_biting: 1000, mustache: 1500, hair_pulling: 1500, face_touch: 1500 };
    var ORDER = ["nail_biting", "mustache", "hair_pulling", "face_touch"];
    var timers = [];
    var index = 0;
    var holdAutoUntil = 0;
    var visible = false;

    function later(fn, ms) {
      timers.push(window.setTimeout(fn, ms));
    }

    function cancel() {
      timers.forEach(window.clearTimeout);
      timers = [];
    }

    function target(habit) {
      var raw = figure.getAttribute("data-" + habit.replace(/_/g, "-")) || "300,300";
      return raw.split(",").map(Number);
    }

    function message(name, habit) {
      var text = figure.getAttribute("data-msg-" + name) || "";
      var chip = chips.filter(function (c) {
        return c.getAttribute("data-habit") === habit;
      })[0];
      return text.replace("{habit}", chip ? chip.getAttribute("data-name") : "");
    }

    function say(name, habit) {
      if (status) status.textContent = message(name, habit);
    }

    function place(point) {
      hand.style.transform = "translate(" + point[0] + "px," + point[1] + "px)";
    }

    function select(habit) {
      figure.setAttribute("data-active", habit || "");
      if (!habit) figure.removeAttribute("data-active");
      chips.forEach(function (chip) {
        chip.setAttribute("aria-pressed", chip.getAttribute("data-habit") === habit ? "true" : "false");
      });
    }

    function lights(habit, on) {
      Object.keys(zones).forEach(function (name) {
        zones[name].classList.toggle("is-hit", on && name === habit);
      });
    }

    function resetRing() {
      ring.classList.remove("dwelling", "done");
      void ring.getBoundingClientRect(); // restart the animation next time
    }

    function release(habit) {
      figure.classList.remove("alarm");
      lights(habit, false);
      resetRing();
      place(REST);
      select("");
      say("away", habit);
    }

    // One full round for a habit: reach, dwell, alarm (or not), release.
    function play(habit) {
      cancel();
      select(habit);
      resetRing();
      figure.classList.remove("alarm");
      var armed = habit !== "face_touch";
      if (reduceMotion.matches) {
        place(target(habit));
        lights(habit, true);
        ring.classList.add("done");
        figure.classList.toggle("alarm", armed);
        say(armed ? "alarm" : "off", habit);
        return;
      }
      place(target(habit));
      later(function () {
        lights(habit, true);
        ring.style.setProperty("--dwell", DWELL[habit] + "ms");
        ring.classList.add("dwelling");
        say("dwell", habit);
      }, 700);
      later(function () {
        ring.classList.remove("dwelling");
        ring.classList.add("done");
        if (armed) {
          figure.classList.add("alarm");
          say("alarm", habit);
        } else {
          say("off", habit);
        }
      }, 700 + DWELL[habit]);
      later(function () {
        release(habit);
      }, 700 + DWELL[habit] + 2400);
      later(next, 700 + DWELL[habit] + 2400 + 1400);
    }

    function next() {
      if (reduceMotion.matches || !visible || document.hidden) return;
      if (Date.now() < holdAutoUntil) {
        later(next, 1000);
        return;
      }
      play(ORDER[index % ORDER.length]);
      index += 1;
    }

    function start() {
      if (timers.length || reduceMotion.matches || !visible || document.hidden) return;
      next();
    }

    chips.forEach(function (chip) {
      chip.addEventListener("click", function () {
        holdAutoUntil = Date.now() + 9000;
        var habit = chip.getAttribute("data-habit");
        index = ORDER.indexOf(habit) + 1;
        play(habit);
      });
    });

    if ("IntersectionObserver" in window) {
      new IntersectionObserver(function (entries) {
        visible = entries[0].isIntersecting;
        if (visible) start();
        else cancel();
      }).observe(figure);
    } else {
      visible = true;
      start();
    }
    document.addEventListener("visibilitychange", function () {
      if (document.hidden) cancel();
      else start();
    });
    if (reduceMotion.addEventListener) {
      reduceMotion.addEventListener("change", function () {
        cancel();
        if (!reduceMotion.matches) start();
      });
    }

    place(REST);
    say("watch");
    window.requestAnimationFrame(function () {
      figure.classList.add("ready");
    });
  }
})();
