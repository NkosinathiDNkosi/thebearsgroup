/* ===============================
   THE BEARS HEALTHCARE INTERACTIONS
================================= */

/* NAVBAR SCROLL EFFECT */
window.addEventListener("scroll", function () {
    const header = document.querySelector("header");
    header.classList.toggle("scrolled", window.scrollY > 50);
});

/* SERVICE DETAILS TOGGLE */
function toggleDetails(id) {
    const element = document.getElementById(id);
    element.classList.toggle("hidden");
}

/* CAROUSEL */
const carousel = document.getElementById("carousel");
const totalSlides = carousel.children.length;
let index = 0;
let interval;

function updateSlide() {
    carousel.style.transform = `translateX(-${index * 100}%)`;
}

function nextSlide() {
    index = (index + 1) % totalSlides;
    updateSlide();
}

function prevSlide() {
    index = (index - 1 + totalSlides) % totalSlides;
    updateSlide();
}

function startAutoSlide() {
    interval = setInterval(nextSlide, 5000);
}

function stopAutoSlide() {
    clearInterval(interval);
}

if (carousel) {
    const wrapper = carousel.parentElement;
    wrapper.addEventListener("mouseenter", stopAutoSlide);
    wrapper.addEventListener("mouseleave", startAutoSlide);
    startAutoSlide();
}

/* ANIMATED STATS COUNTER */
const counters = document.querySelectorAll(".text-3xl");

counters.forEach(counter => {
    const target = +counter.innerText;
    if (!isNaN(target)) {
        let count = 0;
        const increment = target / 100;

        const updateCounter = () => {
            if (count < target) {
                count += increment;
                counter.innerText = Math.ceil(count);
                setTimeout(updateCounter, 20);
            } else {
                counter.innerText = target;
            }
        };

        updateCounter();
    }
});

/* SCROLL FADE-IN ANIMATION */
const faders = document.querySelectorAll(".fade-in");

const appearOptions = {
    threshold: 0.3
};

const appearOnScroll = new IntersectionObserver(function(entries, observer) {
    entries.forEach(entry => {
        if (!entry.isIntersecting) return;
        entry.target.classList.add("visible");
        observer.unobserve(entry.target);
    });
}, appearOptions);

faders.forEach(fader => {
    appearOnScroll.observe(fader);
});