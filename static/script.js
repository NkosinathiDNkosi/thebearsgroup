/* ===============================
   THE BEARS HEALTHCARE INTERACTIONS
================================= */

document.addEventListener("DOMContentLoaded", function () {

    /* ===============================
       NAVBAR SCROLL EFFECT
    ================================= */
    window.addEventListener("scroll", function () {
        const header = document.querySelector("header");
        if (header) {
            header.classList.toggle("scrolled", window.scrollY > 50);
        }
    });

    /* ===============================
       SERVICE DETAILS TOGGLE
    ================================= */
    window.toggleDetails = function (id) {
        const element = document.getElementById(id);
        if (element) {
            element.classList.toggle("hidden");
        }
    };

    /* ===============================
       SERVICE SEARCH / FILTER
    ================================= */
    const serviceSearchInput = document.getElementById("serviceSearch");
    const serviceCards = document.querySelectorAll(".service-card");

    function filterServices() {
        if (!serviceSearchInput || !serviceCards.length) return;

        const query = serviceSearchInput.value.trim().toLowerCase();

        serviceCards.forEach(card => {
            const text = card.innerText.toLowerCase();
            card.style.display = text.includes(query) ? "" : "none";
        });
    }

    if (serviceSearchInput) {
        serviceSearchInput.addEventListener("input", filterServices);
    }

    /* ===============================
       CAROUSELS
    ================================= */
    function createCarousel(carouselId, nextBtnName, prevBtnName) {
        const carousel = document.getElementById(carouselId);

        if (!carousel) return;

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
            interval = setInterval(nextSlide, 2500);
        }

        function stopAutoSlide() {
            clearInterval(interval);
        }

        const wrapper = carousel.parentElement;
        if (wrapper) {
            wrapper.addEventListener("mouseenter", stopAutoSlide);
            wrapper.addEventListener("mouseleave", startAutoSlide);
        }

        startAutoSlide();

        window[nextBtnName] = nextSlide;
        window[prevBtnName] = prevSlide;
    }

    createCarousel("carousel1", "nextSlide1", "prevSlide1");
    createCarousel("carousel2", "nextSlide2", "prevSlide2");

    /* ===============================
       DATE RESTRICTIONS
    ================================= */
    const dateInput = document.querySelector('input[name="appointment_date"]');
    const timeSelect = document.getElementById("appointment_time");
    const helper = document.getElementById("timeSlotHelper");

    function getTodayLocalDate() {
        const now = new Date();
        const year = now.getFullYear();
        const month = String(now.getMonth() + 1).padStart(2, "0");
        const day = String(now.getDate()).padStart(2, "0");
        return `${year}-${month}-${day}`;
    }

    if (dateInput) {
        dateInput.min = getTodayLocalDate();

        dateInput.addEventListener("change", function () {
            const selectedDate = new Date(this.value + "T00:00:00");
            const day = selectedDate.getDay();

            if (day === 0) {
                this.setCustomValidity("Sundays are unavailable. Please choose another date.");
                this.reportValidity();
                if (timeSelect) {
                    timeSelect.innerHTML = `<option value="">Choose a time...</option>`;
                }
                if (helper) {
                    helper.textContent = "Sundays are unavailable. Please choose another date.";
                }
                return;
            } else {
                this.setCustomValidity("");
            }

            fetchBookedSlots(this.value);
        });
    }

    /* ===============================
       REAL-TIME BOOKED SLOTS FROM FLASK
    ================================= */
    const standardSlots = [
        "08:00", "08:30", "09:00", "09:30",
        "10:00", "10:30", "11:00", "11:30",
        "12:00", "12:30", "13:00", "13:30",
        "14:00", "14:30", "15:00", "15:30",
        "16:00", "16:30", "17:00"
    ];

    async function fetchBookedSlots(selectedDate) {
        if (!timeSelect || !selectedDate) return;

        timeSelect.innerHTML = `<option value="">Loading available times...</option>`;

        try {
            const response = await fetch(`/booked-slots?date=${encodeURIComponent(selectedDate)}`);
            const booked = await response.json();

            buildTimeOptions(booked);

            if (helper) {
                if (booked.length > 0) {
                    helper.textContent = `Booked times: ${booked.join(", ")}`;
                } else {
                    helper.textContent = "All standard time slots are currently available.";
                }
            }
        } catch (error) {
            timeSelect.innerHTML = `<option value="">Choose a time...</option>`;
            if (helper) {
                helper.textContent = "Could not load time slots. Please try again.";
            }
        }
    }

    function buildTimeOptions(bookedTimes) {
        if (!timeSelect) return;

        timeSelect.innerHTML = `<option value="">Choose a time...</option>`;

        standardSlots.forEach(time => {
            const option = document.createElement("option");
            option.value = time;
            option.textContent = bookedTimes.includes(time) ? `${time} — Unavailable` : time;
            option.disabled = bookedTimes.includes(time);
            timeSelect.appendChild(option);
        });
    }

   /* ===============================
   FORM VALIDATION IMPROVEMENTS
================================= */
const bookingForm = document.querySelector('form[action="/book"]');
const fullNameInput = document.querySelector('input[name="full_name"]');
const phoneInput = document.querySelector('input[name="phone"]');
const emailInput = document.querySelector('input[name="email"]');
const serviceInput = document.querySelector('select[name="service"]');
const dateInputField = document.querySelector('input[name="appointment_date"]');
const timeSelectField = document.querySelector('[name="appointment_time"]');
const messageInput = document.querySelector('textarea[name="message"]');
const formMessage = document.getElementById("formMessage");

function showFormMessage(message, type = "error") {
    if (!formMessage) return;

    formMessage.textContent = message;
    formMessage.classList.remove("hidden", "bg-red-50", "border-red-200", "text-red-700", "bg-green-50", "border-green-200", "text-green-700");
    formMessage.classList.add("border");

    if (type === "error") {
        formMessage.classList.add("bg-red-50", "border-red-200", "text-red-700");
    } else {
        formMessage.classList.add("bg-green-50", "border-green-200", "text-green-700");
    }
}

function clearFormMessage() {
    if (!formMessage) return;
    formMessage.classList.add("hidden");
    formMessage.textContent = "";
}

function isOnlySpaces(value) {
    return value.trim().length === 0;
}

function normalizePhone(phone) {
    return phone.replace(/\s+/g, "").replace(/[^\d+]/g, "");
}

function validateFullName() {
    if (!fullNameInput) return true;

    const value = fullNameInput.value;

    if (isOnlySpaces(value)) {
        fullNameInput.setCustomValidity("Full name cannot be empty or spaces only.");
        return false;
    }

    if (value.trim().length < 3) {
        fullNameInput.setCustomValidity("Please enter your full name correctly.");
        return false;
    }

    fullNameInput.setCustomValidity("");
    return true;
}

function validatePhone() {
    if (!phoneInput) return true;

    const rawValue = phoneInput.value;
    const value = normalizePhone(rawValue);

    if (isOnlySpaces(rawValue)) {
        phoneInput.setCustomValidity("Phone number cannot be empty or spaces only.");
        return false;
    }

    // South African format: 0XXXXXXXXX or +27XXXXXXXXX
    const valid = /^(\+27\d{9}|0\d{9})$/.test(value);

    if (!valid) {
        phoneInput.setCustomValidity("Enter a valid South African phone number, e.g. 0712345678 or +27712345678.");
        return false;
    }

    phoneInput.setCustomValidity("");
    return true;
}

function validateEmail() {
    if (!emailInput) return true;

    const value = emailInput.value;

    if (isOnlySpaces(value)) {
        emailInput.setCustomValidity("Email address cannot be empty or spaces only.");
        return false;
    }

    const trimmed = value.trim();
    const valid = /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(trimmed);

    if (!valid) {
        emailInput.setCustomValidity("Please enter a valid email address, e.g. name@example.com.");
        return false;
    }

    emailInput.setCustomValidity("");
    return true;
}

function validateService() {
    if (!serviceInput) return true;

    if (!serviceInput.value.trim()) {
        serviceInput.setCustomValidity("Please select a service before continuing.");
        return false;
    }

    serviceInput.setCustomValidity("");
    return true;
}

function validateDateField() {
    if (!dateInputField) return true;

    if (!dateInputField.value) {
        dateInputField.setCustomValidity("Please choose a preferred appointment date.");
        return false;
    }

    const selectedDate = new Date(dateInputField.value + "T00:00:00");
    const today = new Date();
    today.setHours(0, 0, 0, 0);

    if (selectedDate < today) {
        dateInputField.setCustomValidity("You cannot choose a past date.");
        return false;
    }

    if (selectedDate.getDay() === 0) {
        dateInputField.setCustomValidity("Sundays are unavailable. Please choose another date.");
        return false;
    }

    dateInputField.setCustomValidity("");
    return true;
}

function validateTimeField() {
    if (!timeSelectField) return true;

    if (!timeSelectField.value) {
        timeSelectField.setCustomValidity("Please choose an available appointment time.");
        return false;
    }

    timeSelectField.setCustomValidity("");
    return true;
}

function validateMessageField() {
    if (!messageInput) return true;

    const value = messageInput.value;

    if (value.length > 0 && isOnlySpaces(value)) {
        messageInput.setCustomValidity("Additional information cannot contain spaces only.");
        return false;
    }

    messageInput.setCustomValidity("");
    return true;
}

function validateBookingForm() {
    const checks = [
        validateFullName(),
        validatePhone(),
        validateEmail(),
        validateService(),
        validateDateField(),
        validateTimeField(),
        validateMessageField()
    ];

    return checks.every(Boolean);
}

[
    fullNameInput,
    phoneInput,
    emailInput,
    serviceInput,
    dateInputField,
    timeSelectField,
    messageInput
].forEach(field => {
    if (!field) return;

    field.addEventListener("input", function () {
        clearFormMessage();

        if (field === fullNameInput) validateFullName();
        if (field === phoneInput) validatePhone();
        if (field === emailInput) validateEmail();
        if (field === serviceInput) validateService();
        if (field === dateInputField) validateDateField();
        if (field === timeSelectField) validateTimeField();
        if (field === messageInput) validateMessageField();
    });

    field.addEventListener("change", function () {
        clearFormMessage();

        if (field === fullNameInput) validateFullName();
        if (field === phoneInput) validatePhone();
        if (field === emailInput) validateEmail();
        if (field === serviceInput) validateService();
        if (field === dateInputField) validateDateField();
        if (field === timeSelectField) validateTimeField();
        if (field === messageInput) validateMessageField();
    });
});

if (bookingForm) {
    bookingForm.addEventListener("submit", function (e) {
        clearFormMessage();

        const isValid = validateBookingForm();

        if (!isValid) {
            e.preventDefault();

            showFormMessage("Please correct the highlighted fields before submitting.", "error");
            bookingForm.reportValidity();
            return;
        }

        const submitBtn = bookingForm.querySelector('button[type="submit"]');
        if (submitBtn) {
            submitBtn.disabled = true;
            submitBtn.dataset.originalText = submitBtn.innerHTML;
            submitBtn.innerHTML = "Submitting...";
            submitBtn.classList.add("opacity-80", "cursor-not-allowed");
        }
    });
}
    /* ===============================
       PREMIUM COUNTERS
    ================================= */
    const counters = document.querySelectorAll(".counter");
    let countersStarted = false;

    function animateCounter(counter, duration = 1800) {
        const target = parseInt(counter.getAttribute("data-target"), 10) || 0;
        const startTime = performance.now();

        function easeOutCubic(t) {
            return 1 - Math.pow(1 - t, 3);
        }

        function update(currentTime) {
            const elapsed = currentTime - startTime;
            const progress = Math.min(elapsed / duration, 1);
            const easedProgress = easeOutCubic(progress);
            const currentValue = Math.round(target * easedProgress);

            counter.textContent = currentValue;

            if (progress < 1) {
                requestAnimationFrame(update);
            } else {
                counter.textContent = target;
            }
        }

        requestAnimationFrame(update);
    }

    function runCounters() {
        counters.forEach(counter => animateCounter(counter));
    }

    const counterSection = document.querySelector(".counter")?.closest("section");

    if (counterSection) {
        const observer = new IntersectionObserver((entries) => {
            entries.forEach(entry => {
                if (entry.isIntersecting && !countersStarted) {
                    countersStarted = true;
                    runCounters();
                }
            });
        }, { threshold: 0.3 });

        observer.observe(counterSection);
    }

    /* ===============================
       SCROLL FADE-IN ANIMATION
    ================================= */
    const faders = document.querySelectorAll(".fade-in");

    const appearOptions = {
        threshold: 0.3
    };

    const appearOnScroll = new IntersectionObserver(function (entries, observer) {
        entries.forEach(entry => {
            if (!entry.isIntersecting) return;
            entry.target.classList.add("visible");
            observer.unobserve(entry.target);
        });
    }, appearOptions);

    faders.forEach(fader => {
        appearOnScroll.observe(fader);
    });

});

// Auto hide success message

document.addEventListener("DOMContentLoaded", function () {
  const success = document.getElementById("successMessage");
  const error = document.getElementById("errorMessage");

  function showAndHide(messageBox, visibleTime = 6000) {
    if (!messageBox) return;

    // slide in
    setTimeout(() => {
      messageBox.classList.remove("opacity-0", "-translate-y-4");
      messageBox.classList.add("opacity-100", "translate-y-0");
    }, 100);

    // slide out
    setTimeout(() => {
      messageBox.classList.remove("opacity-100", "translate-y-0");
      messageBox.classList.add("opacity-0", "-translate-y-4");

      setTimeout(() => {
        messageBox.style.display = "none";
      }, 700);
    }, visibleTime);
  }

  showAndHide(success, 6000);
  showAndHide(error, 7000);
});
