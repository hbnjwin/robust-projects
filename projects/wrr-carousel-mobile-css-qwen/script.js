let current = 0;
const slides = document.querySelectorAll(".slide");

function showSlide(n) {
  slides[current].classList.remove("active");
  current = (n + slides.length) % slides.length;
  slides[current].classList.add("active");
  // BUG: no smooth transition, causes flash
}

document.querySelector(".next").addEventListener("click", () => showSlide(current + 1));
document.querySelector(".prev").addEventListener("click", () => showSlide(current - 1));
