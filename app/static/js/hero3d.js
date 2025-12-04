document.addEventListener("DOMContentLoaded", () => {
  const card = document.getElementById("hero-3d-card");
  if (!card) return;

  const inner = card.querySelector(".hero-3d-inner");
  let flipped = false;

  const updateTransform = (e) => {
    const rect = card.getBoundingClientRect();
    const x = e.clientX - rect.left - rect.width / 2;
    const y = e.clientY - rect.top - rect.height / 2;
    const rotateX = (-y / rect.height) * 20;
    const rotateY = (x / rect.width) * 20;
    inner.style.transform = `rotateY(${flipped ? 180 : 0}deg) rotateX(${rotateX}deg) rotateY(${rotateY}deg)`;
  };

  card.addEventListener("mousemove", updateTransform);
  card.addEventListener("mouseleave", () => {
    inner.style.transform = `rotateY(${flipped ? 180 : 0}deg) rotateX(0deg) rotateY(0deg)`;
  });

  card.addEventListener("click", () => {
    flipped = !flipped;
    inner.style.transform = `rotateY(${flipped ? 180 : 0}deg) rotateX(0deg) rotateY(0deg)`;
  });
});
