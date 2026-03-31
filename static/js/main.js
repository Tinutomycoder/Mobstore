document.addEventListener('DOMContentLoaded', () => {
  const filterForm = document.getElementById('filterForm');
  if (filterForm) {
    const categoryInput = filterForm.querySelector('select[name="category"]');
    if (categoryInput) {
      categoryInput.addEventListener('change', () => filterForm.submit());
    }
  }

  const cartForms = document.querySelectorAll('.cart-update-form');
  cartForms.forEach((form) => {
    const qtyInput = form.querySelector('.cart-qty');
    if (!qtyInput) return;
    qtyInput.addEventListener('change', () => {
      if (Number(qtyInput.value) < 1) qtyInput.value = 1;
    });
  });
});
