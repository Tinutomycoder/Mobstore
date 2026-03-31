from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import user_passes_test
from django.contrib.auth.models import User
from django.shortcuts import get_object_or_404, redirect, render

from .cart import SessionCart
from .forms import LoginForm, RegisterForm
from .models import Category, Product


def home(request):
    query = request.GET.get('q', '').strip()
    products = Product.objects.filter(available=True)
    if query:
        products = products.filter(name__icontains=query)
    return render(request, 'home.html', {'products': products[:8], 'search_query': query})


def products(request):
    query = request.GET.get('q', '').strip()
    category_slug = request.GET.get('category', '').strip()
    product_qs = Product.objects.filter(available=True)
    if query:
        product_qs = product_qs.filter(name__icontains=query)
    if category_slug:
        product_qs = product_qs.filter(category__slug=category_slug)
    return render(
        request,
        'products.html',
        {
            'products': product_qs,
            'categories': Category.objects.all(),
            'query': query,
            'search_query': query,
            'current_category': category_slug,
        },
    )


def product_detail(request, product_id):
    product = get_object_or_404(Product, id=product_id, available=True)
    related = Product.objects.filter(category=product.category, available=True).exclude(id=product.id)[:4]
    return render(request, 'product_detail.html', {'product': product, 'related': related})


def cart_view(request):
    cart = SessionCart(request)
    return render(request, 'cart.html', {'items': cart.get_items(), 'total': cart.get_total()})


def add_to_cart(request, product_id):
    if request.method == 'POST':
        product = get_object_or_404(Product, id=product_id)
        quantity = max(1, int(request.POST.get('quantity', 1)))
        SessionCart(request).add(product, quantity)
        messages.success(request, f'"{product.name}" added to your cart.')
    return redirect('cart')


def remove_from_cart(request, product_id):
    if request.method == 'POST':
        product = get_object_or_404(Product, id=product_id)
        SessionCart(request).remove(product)
        messages.info(request, f'"{product.name}" removed from your cart.')
    return redirect('cart')


def update_cart(request, product_id):
    if request.method == 'POST':
        product = get_object_or_404(Product, id=product_id)
        quantity = int(request.POST.get('quantity', 1))
        SessionCart(request).update(product, quantity)
    return redirect('cart')


def login_view(request):
    if request.user.is_authenticated:
        return redirect('home')

    form = LoginForm(request.POST or None)
    next_url = request.GET.get('next', '')
    if request.method == 'POST':
        next_url = request.POST.get('next', next_url)
        if form.is_valid():
            user = authenticate(
                request,
                username=form.cleaned_data['username'],
                password=form.cleaned_data['password'],
            )
            if user is not None:
                login(request, user)
                messages.success(request, f'Welcome back, {user.username}!')
                if next_url and next_url.startswith('/'):
                    return redirect(next_url)
                return redirect('home')
            messages.error(request, 'Invalid username or password.')

    return render(request, 'login.html', {'form': form, 'next': next_url})


def register_view(request):
    if request.user.is_authenticated:
        return redirect('home')

    form = RegisterForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        user = form.save()
        login(request, user)
        messages.success(request, f'Account created. Welcome, {user.username}!')
        return redirect('home')

    return render(request, 'register.html', {'form': form})


def logout_view(request):
    logout(request)
    messages.info(request, 'You have been logged out.')
    return redirect('home')


def customer_admin_login(request):
    if request.user.is_authenticated and request.user.is_staff:
        return redirect('customer_admin_panel')

    form = LoginForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        user = authenticate(
            request,
            username=form.cleaned_data['username'],
            password=form.cleaned_data['password'],
        )
        if user is None:
            messages.error(request, 'Invalid username or password.')
        elif not user.is_staff:
            messages.error(request, 'Access denied. Staff account required.')
        else:
            login(request, user)
            messages.success(request, f'Welcome to customer admin panel, {user.username}.')
            return redirect('customer_admin_panel')

    return render(request, 'customer_admin_login.html', {'form': form})


@user_passes_test(lambda user: user.is_authenticated and user.is_staff, login_url='customer_admin_login')
def customer_admin_panel(request):
    customers = User.objects.filter(is_staff=False, is_superuser=False).order_by('-date_joined')
    return render(request, 'customer_admin_panel.html', {'customers': customers})
