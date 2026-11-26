import json
from datetime import datetime
from decimal import Decimal, InvalidOperation
from urllib.parse import quote

from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.models import User
from django.db import transaction
from django.db.models import Avg, Count, DecimalField, F, Q, Sum
from django.db.models.functions import TruncDate, TruncMonth
from django.http import HttpResponse
from django.urls import reverse
from django.utils import timezone
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.http import require_http_methods, require_POST

from .forms import (
    AdminUserEditForm,
    CategoryForm,
    LoginForm,
    ProductForm,
    ProductReviewForm,
    ProfileForm,
    RegisterForm,
)
from .models import Cart, Category, Order, OrderItem, Product, ProductReview, UserProfile


def is_staff_user(user):
    return user.is_authenticated and user.is_staff


ADMIN_ORDER_STATUS_CODES = ('processing', 'shipped', 'delivered', 'cancelled')
REVIEWABLE_ORDER_STATUS_CODES = ('processing', 'shipped', 'delivered')


def home(request):
    featured_products = Product.objects.select_related('category')[:8]
    categories = Category.objects.annotate(total_products=Count('products'))
    return render(
        request,
        'store/home.html',
        {'featured_products': featured_products, 'categories': categories},
    )


def _apply_text_search(queryset, query):
    # Match per-word so minor spacing/punctuation differences don't break search.
    terms = [term for term in query.replace('(', ' ').replace(')', ' ').split() if term]
    for term in terms:
        queryset = queryset.filter(Q(name__icontains=term) | Q(brand__icontains=term))
    return queryset


def _apply_product_filters(request, queryset):
    query = request.GET.get('q', '').strip()
    category_slug = request.GET.get('category', '').strip()
    min_price = request.GET.get('min_price', '').strip()
    max_price = request.GET.get('max_price', '').strip()

    if query:
        queryset = _apply_text_search(queryset, query)
    if category_slug:
        queryset = queryset.filter(category__slug=category_slug)
    if min_price:
        try:
            queryset = queryset.filter(price__gte=Decimal(min_price))
        except InvalidOperation:
            min_price = ''
    if max_price:
        try:
            queryset = queryset.filter(price__lte=Decimal(max_price))
        except InvalidOperation:
            max_price = ''

    return queryset, query, category_slug, min_price, max_price


def products(request):
    queryset = Product.objects.select_related('category')
    queryset, query, category_slug, min_price, max_price = _apply_product_filters(request, queryset)
    return render(
        request,
        'store/products.html',
        {
            'products': queryset,
            'query': query,
            'current_category': category_slug,
            'min_price': min_price,
            'max_price': max_price,
            'categories': Category.objects.all(),
        },
    )


def products_by_category(request, slug):
    queryset = Product.objects.select_related('category').filter(category__slug=slug)
    query = request.GET.get('q', '').strip()
    min_price = request.GET.get('min_price', '').strip()
    max_price = request.GET.get('max_price', '').strip()
    if query:
        queryset = _apply_text_search(queryset, query)
    if min_price:
        try:
            queryset = queryset.filter(price__gte=Decimal(min_price))
        except InvalidOperation:
            min_price = ''
    if max_price:
        try:
            queryset = queryset.filter(price__lte=Decimal(max_price))
        except InvalidOperation:
            max_price = ''
    return render(
        request,
        'store/products.html',
        {
            'products': queryset,
            'query': query,
            'current_category': slug,
            'min_price': min_price,
            'max_price': max_price,
            'categories': Category.objects.all(),
        },
    )


def search_results(request):
    queryset = Product.objects.select_related('category')
    queryset, query, category_slug, min_price, max_price = _apply_product_filters(request, queryset)
    return render(
        request,
        'store/search_results.html',
        {
            'products': queryset,
            'query': query,
            'current_category': category_slug,
            'min_price': min_price,
            'max_price': max_price,
            'categories': Category.objects.all(),
        },
    )


def product_detail(request, pk):
    product = get_object_or_404(Product.objects.select_related('category'), pk=pk)
    related_products = Product.objects.filter(category=product.category).exclude(pk=product.pk)[:4]
    reviews = product.reviews.select_related('user')
    review_summary = reviews.aggregate(avg_rating=Avg('rating'), total_reviews=Count('id'))
    can_review = False
    if request.user.is_authenticated:
        can_review = OrderItem.objects.filter(
            order__user=request.user,
            order__status__in=REVIEWABLE_ORDER_STATUS_CODES,
            product=product,
        ).exists()
    return render(
        request,
        'store/product_detail.html',
        {
            'product': product,
            'related_products': related_products,
            'reviews': reviews,
            'review_summary': review_summary,
            'can_review': can_review,
        },
    )


def register_view(request):
    if request.user.is_authenticated:
        return redirect('home')

    form = RegisterForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        user = form.save()
        login(request, user)
        messages.success(request, 'Account created successfully.')
        return redirect('home')
    return render(request, 'store/register.html', {'form': form})


@never_cache
@ensure_csrf_cookie
def login_view(request):
    if request.user.is_authenticated:
        return redirect('home')

    form = LoginForm(request.POST or None)
    form.fields['username'].widget.attrs.update({'autocomplete': 'off', 'autocapitalize': 'none', 'spellcheck': 'false'})
    form.fields['password'].widget.attrs.update({'autocomplete': 'new-password'})
    next_url = request.GET.get('next', '')
    if request.method == 'POST' and form.is_valid():
        next_url = request.POST.get('next', next_url)
        user = authenticate(
            request,
            username=form.cleaned_data['username'],
            password=form.cleaned_data['password'],
        )
        if user is not None:
            login(request, user)
            messages.success(request, f'Welcome back, {user.username}.')
            if next_url.startswith('/'):
                return redirect(next_url)
            return redirect('home')
        messages.error(request, 'Invalid username or password.')
    return render(request, 'store/login.html', {'form': form, 'next': next_url})


@require_http_methods(['GET', 'POST'])
def logout_view(request):
    logout(request)
    messages.info(request, 'Logged out successfully.')
    return redirect('home')


@login_required
def profile_view(request):
    form = ProfileForm(request.POST or None, user=request.user)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, 'Profile updated.')
        return redirect('profile')
    return render(request, 'store/profile.html', {'form': form})


@login_required
def cart_view(request):
    return redirect('checkout')


@login_required
@require_POST
def add_to_cart(request, product_id):
    product = get_object_or_404(Product, pk=product_id)
    quantity = max(1, int(request.POST.get('quantity', 1)))

    if product.stock == 0:
        messages.error(request, f'"{product.name}" is out of stock.')
        return redirect('product_detail', pk=product_id)

    cart_item = Cart.objects.filter(user=request.user, product=product).first()
    if cart_item:
        messages.info(request, 'Item is already in cart.')
        return redirect('checkout')

    quantity = min(quantity, product.stock)
    Cart.objects.create(user=request.user, product=product, quantity=quantity)

    messages.success(request, f'{product.name} added to cart.')
    return redirect('checkout')


@login_required
@require_POST
def update_cart_item(request, item_id):
    item = get_object_or_404(Cart, pk=item_id, user=request.user)
    quantity = int(request.POST.get('quantity', item.quantity))
    if quantity <= 0:
        item.delete()
        messages.info(request, 'Item removed from cart.')
    else:
        stock = item.product.stock
        if quantity > stock:
            messages.error(request, f'Only {stock} unit(s) of "{item.product.name}" available.')
            return redirect('checkout')
        item.quantity = quantity
        item.save(update_fields=['quantity', 'updated_at'])
        messages.success(request, 'Cart updated.')
    return redirect('checkout')


@login_required
@require_POST
def remove_cart_item(request, item_id):
    item = get_object_or_404(Cart, pk=item_id, user=request.user)
    item.delete()
    messages.info(request, 'Item removed from cart.')
    return redirect('checkout')


@login_required
def checkout_view(request):
    items = Cart.objects.select_related('product').filter(user=request.user)
    if not items.exists():
        messages.warning(request, 'Your cart is empty.')
        return redirect('products')

    total = sum(item.total_price for item in items)
    if request.method == 'POST':
        # Validate ALL items before touching the database
        for item in items:
            if item.quantity > item.product.stock:
                messages.error(
                    request,
                    f'Only {item.product.stock} unit(s) of "{item.product.name}" available '
                    f'but your cart has {item.quantity}. Please update your cart.',
                )
                return redirect('cart')

        profile = UserProfile.objects.filter(user=request.user).first()
        delivery_address = profile.delivery_address if profile else ''

        with transaction.atomic():
            order = Order.objects.create(
                user=request.user,
                total_price=total,
                delivery_address=delivery_address,
                status='pending',
            )
            for item in items:
                OrderItem.objects.create(
                    order=order,
                    product=item.product,
                    quantity=item.quantity,
                    price=item.product.price,
                )
                item.product.stock -= item.quantity
                item.product.save(update_fields=['stock'])
            items.delete()
        messages.success(request, f'Order #{order.pk} placed successfully.')
        return redirect('order_history')

    return render(request, 'store/checkout.html', {'items': items, 'total': total})


@login_required
@never_cache
def order_history(request):
    orders = (
        Order.objects.filter(user=request.user)
        .prefetch_related('items__product')
        .order_by('-order_date')
    )
    reviewed_product_ids = set(
        ProductReview.objects.filter(user=request.user).values_list('product_id', flat=True)
    )
    return render(
        request,
        'store/order_history.html',
        {
            'orders': orders,
            'reviewed_product_ids': reviewed_product_ids,
        },
    )


@login_required
def write_review(request, product_id):
    product = get_object_or_404(Product, pk=product_id)

    has_ordered_product = OrderItem.objects.filter(
        order__user=request.user,
        order__status__in=REVIEWABLE_ORDER_STATUS_CODES,
        product=product,
    ).exists()
    if not has_ordered_product:
        messages.error(request, 'You can only review products you have ordered.')
        return redirect('order_history')

    review = ProductReview.objects.filter(user=request.user, product=product).first()

    if request.method == 'POST':
        form = ProductReviewForm(request.POST, instance=review)
        if form.is_valid():
            saved_review = form.save(commit=False)
            saved_review.user = request.user
            saved_review.product = product
            saved_review.save()
            messages.success(request, f'Thanks! Your review for "{product.name}" has been saved.')
            return redirect('product_detail', pk=product.pk)
    else:
        form = ProductReviewForm(instance=review)

    return render(
        request,
        'store/review_form.html',
        {'form': form, 'product': product, 'review': review},
    )


@login_required
@require_POST
def cancel_order(request, pk):
    order = get_object_or_404(Order, pk=pk, user=request.user)
    if order.status not in ('pending', 'processing'):
        messages.error(request, f'Order #{order.pk} cannot be cancelled at this stage.')
        return redirect('order_history')
    with transaction.atomic():
        for item in order.items.select_related('product').all():
            if item.product:
                item.product.stock += item.quantity
                item.product.save(update_fields=['stock'])
        order.status = 'cancelled'
        order.save(update_fields=['status'])
    messages.success(request, f'Order #{order.pk} has been cancelled and stock restored.')
    return redirect('order_history')


@login_required
def order_invoice(request, pk):
    order = get_object_or_404(
        Order.objects.prefetch_related('items__product'),
        pk=pk,
        user=request.user,
        status='delivered',
    )
    return render(request, 'store/invoice.html', {'order': order})


@require_http_methods(["GET", "POST"])
def buy_now(request, product_id):
    """Buy product directly without cart - redirects to payment"""
    if not request.user.is_authenticated:
        messages.info(request, 'Please login to continue with Buy Now.')
        login_url = f"{reverse('login')}?next={quote(request.get_full_path(), safe='/?=&')}"
        return redirect(login_url)

    product = get_object_or_404(Product, pk=product_id)
    quantity_raw = request.POST.get('quantity', 1) if request.method == 'POST' else request.GET.get('quantity', 1)
    try:
        quantity = max(1, int(quantity_raw))
    except (TypeError, ValueError):
        quantity = 1

    if product.stock == 0:
        messages.error(request, f'"{product.name}" is out of stock.')
        return redirect('product_detail', pk=product_id)

    if quantity > product.stock:
        messages.error(request, f'Only {product.stock} unit(s) available.')
        return redirect('product_detail', pk=product_id)

    # Add/update cart item and redirect to payment for this specific item
    cart_item, created = Cart.objects.get_or_create(
        user=request.user,
        product=product,
        defaults={'quantity': quantity},
    )
    if not created:
        cart_item.quantity = quantity
        cart_item.save(update_fields=['quantity', 'updated_at'])

    payment_url = f"{reverse('payment')}?buy_now_item={cart_item.pk}"
    return redirect(payment_url)


@login_required
def payment_view(request):
    buy_now_item_id = (request.POST.get('buy_now_item') or request.GET.get('buy_now_item') or '').strip()
    is_buy_now = False
    buy_now_item = None

    if buy_now_item_id:
        try:
            buy_now_item = Cart.objects.select_related('product').get(
                user=request.user,
                pk=int(buy_now_item_id),
            )
        except (ValueError, Cart.DoesNotExist):
            messages.error(request, 'The selected Buy Now item is no longer available.')
            return redirect('checkout')

        items = Cart.objects.select_related('product').filter(pk=buy_now_item.pk, user=request.user)
        is_buy_now = True
    else:
        items = Cart.objects.select_related('product').filter(user=request.user)

    if not items.exists():
        messages.warning(request, 'Your cart is empty.')
        return redirect('products')

    total = sum(item.total_price for item in items)
    profile, _ = UserProfile.objects.get_or_create(user=request.user)
    saved_delivery_address = (profile.delivery_address or '').strip()
    saved_phone_number = (profile.phone_number or '').strip()

    if request.method == 'POST':
        delivery_address = request.POST.get('delivery_address', '').strip()
        if not delivery_address:
            messages.error(request, 'Please provide a delivery address before payment.')
            return redirect(request.get_full_path())

        # Validate stock before creating order
        for item in items:
            if item.quantity > item.product.stock:
                messages.error(
                    request,
                    f'Only {item.product.stock} unit(s) of "{item.product.name}" available. Please update your cart.',
                )
                return redirect('cart')

        # Create order and clear cart
        with transaction.atomic():
            order = Order.objects.create(
                user=request.user,
                total_price=total,
                delivery_address=delivery_address,
                status='pending',
            )
            for item in items:
                OrderItem.objects.create(
                    order=order,
                    product=item.product,
                    quantity=item.quantity,
                    price=item.product.price,
                )
                item.product.stock -= item.quantity
                item.product.save(update_fields=['stock'])
            items.delete()

        messages.success(request, f'Order #{order.pk} placed successfully!')
        return redirect('order_history')

    return render(
        request,
        'store/payment.html',
        {
            'items': items,
            'total': total,
            'is_buy_now': is_buy_now,
            'buy_now_item': buy_now_item,
            'delivery_address': saved_delivery_address,
            'phone_number': saved_phone_number,
        },
    )


def admin_login(request):
    if request.user.is_authenticated and request.user.is_staff:
        return redirect('admin_dashboard')
    form = LoginForm(request.POST or None)
    next_url = request.GET.get('next', '')
    # Prevent browser autofill on admin credentials fields.
    form.fields['username'].widget.attrs.update({'autocomplete': 'off', 'autocapitalize': 'none'})
    form.fields['password'].widget.attrs.update({'autocomplete': 'new-password'})
    if request.method == 'POST' and form.is_valid():
        next_url = request.POST.get('next', next_url)
        user = authenticate(
            request,
            username=form.cleaned_data['username'],
            password=form.cleaned_data['password'],
        )
        if user is None:
            messages.error(request, 'Invalid username or password.')
        elif not user.is_staff:
            messages.error(request, 'This account does not have admin access.')
        else:
            login(request, user)
            if next_url.startswith('/'):
                return redirect(next_url)
            return redirect('admin_dashboard')
    return render(request, 'admin_panel/login.html', {'form': form, 'next': next_url})


@require_POST
def admin_logout(request):
    logout(request)
    return redirect('admin_login')


@user_passes_test(is_staff_user, login_url='admin_login')
def admin_dashboard(request):
    total_products = Product.objects.count()
    total_orders = Order.objects.count()
    total_users = User.objects.filter(is_staff=False).count()
    total_sales = Order.objects.exclude(status='cancelled').aggregate(total=Sum('total_price'))['total'] or 0
    total_reviews = ProductReview.objects.count()
    avg_review_rating = ProductReview.objects.aggregate(avg=Avg('rating'))['avg'] or 0
    reviews_with_comment = ProductReview.objects.exclude(comment='').count()
    latest_orders = Order.objects.select_related('user')[:6]
    latest_reviews = ProductReview.objects.select_related('user', 'product').order_by('-updated_at')[:8]

    # Monthly sales for the last 12 months
    twelve_months_ago = timezone.now() - timezone.timedelta(days=365)
    monthly_sales = (
        Order.objects.exclude(status='cancelled')
        .filter(order_date__gte=twelve_months_ago)
        .annotate(month=TruncMonth('order_date'))
        .values('month')
        .annotate(total=Sum('total_price'), count=Count('id'))
        .order_by('month')
    )

    chart_labels = [entry['month'].strftime('%b %Y') for entry in monthly_sales]
    chart_sales = [float(entry['total']) for entry in monthly_sales]
    chart_orders = [entry['count'] for entry in monthly_sales]

    # Top products by quantity sold
    top_products = (
        OrderItem.objects.values('product__name')
        .annotate(total_quantity=Sum('quantity'), total_revenue=Sum('price'))
        .order_by('-total_quantity')[:10]
    )
    
    product_labels = [item['product__name'] for item in top_products]
    product_quantities = [item['total_quantity'] for item in top_products]
    product_revenues = [float(item['total_revenue']) for item in top_products]

    return render(
        request,
        'admin_panel/dashboard.html',
        {
            'total_products': total_products,
            'total_orders': total_orders,
            'total_users': total_users,
            'total_sales': total_sales,
            'total_reviews': total_reviews,
            'avg_review_rating': avg_review_rating,
            'reviews_with_comment': reviews_with_comment,
            'latest_orders': latest_orders,
            'latest_reviews': latest_reviews,
            'chart_labels': json.dumps(chart_labels),
            'chart_sales': json.dumps(chart_sales),
            'chart_orders': json.dumps(chart_orders),
            'product_labels': json.dumps(product_labels),
            'product_quantities': json.dumps(product_quantities),
            'product_revenues': json.dumps(product_revenues),
        },
    )


@user_passes_test(is_staff_user, login_url='admin_login')
def admin_sales_report(request):
    today = timezone.localdate()
    default_start = today - timezone.timedelta(days=29)

    start_raw = request.GET.get('start_date', '')
    end_raw = request.GET.get('end_date', '')
    selected_status = request.GET.get('status', 'all')
    export_type = request.GET.get('export', '')

    def _parse_date(value, fallback):
        if not value:
            return fallback
        try:
            return datetime.strptime(value, '%Y-%m-%d').date()
        except ValueError:
            messages.error(request, f'Invalid date "{value}". Using default range instead.')
            return fallback

    start_date = _parse_date(start_raw, default_start)
    end_date = _parse_date(end_raw, today)
    if start_date > end_date:
        start_date, end_date = end_date, start_date

    valid_status_codes = {code for code, _label in Order.STATUS_CHOICES}
    if selected_status not in valid_status_codes and selected_status != 'all':
        selected_status = 'all'

    orders_qs = (
        Order.objects.select_related('user')
        .prefetch_related('items__product')
        .filter(order_date__date__gte=start_date, order_date__date__lte=end_date)
    )
    if selected_status != 'all':
        orders_qs = orders_qs.filter(status=selected_status)

    non_cancelled_orders = orders_qs.exclude(status='cancelled')
    report_totals = orders_qs.aggregate(
        gross_sales=Sum('total_price'),
        total_orders=Count('id'),
        cancelled_orders=Count('id', filter=Q(status='cancelled')),
    )
    net_sales = non_cancelled_orders.aggregate(net=Sum('total_price'))['net'] or Decimal('0')
    avg_order_value = non_cancelled_orders.aggregate(avg=Avg('total_price'))['avg'] or Decimal('0')

    daily_summary = (
        non_cancelled_orders.annotate(day=TruncDate('order_date'))
        .values('day')
        .annotate(total_sales=Sum('total_price'), total_orders=Count('id'))
        .order_by('day')
    )
    chart_labels = [entry['day'].strftime('%Y-%m-%d') for entry in daily_summary]
    chart_sales = [float(entry['total_sales']) for entry in daily_summary]
    chart_orders = [entry['total_orders'] for entry in daily_summary]

    top_products = (
        OrderItem.objects.filter(order__in=non_cancelled_orders)
        .values('product__name')
        .annotate(
            total_quantity=Sum('quantity'),
            total_revenue=Sum(F('price') * F('quantity'), output_field=DecimalField(max_digits=14, decimal_places=2)),
        )
        .order_by('-total_quantity')[:10]
    )

    if export_type == 'csv':
        import csv

        response = HttpResponse(content_type='text/csv')
        filename = f'sales_report_{start_date.isoformat()}_to_{end_date.isoformat()}.csv'
        response['Content-Disposition'] = f'attachment; filename="{filename}"'

        writer = csv.writer(response)
        writer.writerow(['Order ID', 'Date', 'Time', 'Customer', 'Status', 'Total (Rs.)'])
        for order in orders_qs.order_by('-order_date'):
            local_dt = timezone.localtime(order.order_date)
            writer.writerow([
                f'#{order.pk}',
                local_dt.strftime('%d/%m/%Y'),
                local_dt.strftime('%H:%M:%S'),
                order.user.username,
                order.get_status_display(),
                order.total_price,
            ])
        return response

    return render(
        request,
        'admin_panel/sales_report.html',
        {
            'orders': orders_qs.order_by('-order_date'),
            'top_products': top_products,
            'status_choices': Order.STATUS_CHOICES,
            'selected_status': selected_status,
            'start_date': start_date.isoformat(),
            'end_date': end_date.isoformat(),
            'report_total_orders': report_totals['total_orders'] or 0,
            'report_cancelled_orders': report_totals['cancelled_orders'] or 0,
            'report_gross_sales': report_totals['gross_sales'] or Decimal('0'),
            'report_net_sales': net_sales,
            'report_avg_order_value': avg_order_value,
            'chart_labels': json.dumps(chart_labels),
            'chart_sales': json.dumps(chart_sales),
            'chart_orders': json.dumps(chart_orders),
        },
    )


@user_passes_test(is_staff_user, login_url='admin_login')
def admin_products(request):
    products_qs = Product.objects.select_related('category')
    return render(request, 'admin_panel/products.html', {'products': products_qs})


@user_passes_test(is_staff_user, login_url='admin_login')
def admin_product_add(request):
    form = ProductForm(request.POST or None, request.FILES or None)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, 'Product added.')
        return redirect('admin_products')
    return render(request, 'admin_panel/product_form.html', {'form': form, 'title': 'Add Product'})


@user_passes_test(is_staff_user, login_url='admin_login')
def admin_product_edit(request, pk):
    product = get_object_or_404(Product, pk=pk)
    form = ProductForm(request.POST or None, request.FILES or None, instance=product)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, 'Product updated.')
        return redirect('admin_products')
    return render(request, 'admin_panel/product_form.html', {'form': form, 'title': 'Edit Product'})


@user_passes_test(is_staff_user, login_url='admin_login')
def admin_product_delete(request, pk):
    product = get_object_or_404(Product, pk=pk)
    if request.method == 'POST':
        name = product.name
        product.delete()
        messages.success(request, f'"{name}" has been deleted.')
        return redirect('admin_products')
    return render(
        request,
        'admin_panel/confirm_delete.html',
        {'title': 'Delete Product', 'object_name': product.name},
    )


@user_passes_test(is_staff_user, login_url='admin_login')
def admin_categories(request):
    form = CategoryForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, 'Category added.')
        return redirect('admin_categories')
    categories_qs = Category.objects.all()
    return render(
        request,
        'admin_panel/categories.html',
        {'form': form, 'categories': categories_qs},
    )


@user_passes_test(is_staff_user, login_url='admin_login')
def admin_category_edit(request, pk):
    category = get_object_or_404(Category, pk=pk)
    form = CategoryForm(request.POST or None, instance=category)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, 'Category updated.')
        return redirect('admin_categories')
    categories_qs = Category.objects.all()
    return render(
        request,
        'admin_panel/categories.html',
        {'form': form, 'categories': categories_qs, 'editing': category},
    )


@user_passes_test(is_staff_user, login_url='admin_login')
def admin_category_delete(request, pk):
    category = get_object_or_404(Category, pk=pk)
    if request.method == 'POST':
        category.delete()
        messages.info(request, 'Category deleted.')
        return redirect('admin_categories')
    return render(
        request,
        'admin_panel/confirm_delete.html',
        {'title': 'Delete Category', 'object_name': category.name},
    )


@user_passes_test(is_staff_user, login_url='admin_login')
def admin_orders(request):
    admin_status_choices = [
        choice for choice in Order.STATUS_CHOICES if choice[0] in ADMIN_ORDER_STATUS_CODES
    ]

    if request.method == 'POST':
        order = get_object_or_404(
            Order.objects.prefetch_related('items__product'),
            pk=request.POST.get('order_id'),
        )
        old_status = order.status
        new_status = request.POST.get('status')
        valid_statuses = {choice[0] for choice in admin_status_choices}
        if new_status in valid_statuses and new_status != old_status:
            with transaction.atomic():
                # Cancelling: restore stock
                if new_status == 'cancelled' and old_status != 'cancelled':
                    for item in order.items.select_related('product').all():
                        if item.product:
                            item.product.stock += item.quantity
                            item.product.save(update_fields=['stock'])
                # Reactivating from cancelled: deduct stock back
                elif old_status == 'cancelled' and new_status != 'cancelled':
                    for item in order.items.select_related('product').all():
                        if item.product:
                            if item.quantity > item.product.stock:
                                messages.error(
                                    request,
                                    f'Not enough stock for "{item.product.name}" '
                                    f'(available: {item.product.stock}, needed: {item.quantity}). '
                                    f'Update stock before reactivating.',
                                )
                                return redirect('admin_orders')
                            item.product.stock -= item.quantity
                            item.product.save(update_fields=['stock'])
                order.status = new_status
                order.save(update_fields=['status'])
            messages.success(request, f'Order #{order.pk} status updated to {new_status}.')
        elif new_status not in valid_statuses:
            messages.error(request, 'Invalid status selection.')
        return redirect('admin_orders')
    orders_qs = Order.objects.select_related('user').prefetch_related('items__product')
    return render(
        request,
        'admin_panel/orders.html',
        {'orders': orders_qs, 'status_choices': admin_status_choices},
    )


@user_passes_test(is_staff_user, login_url='admin_login')
def admin_users(request):
    users = User.objects.all().order_by('-date_joined')
    return render(request, 'admin_panel/users.html', {'users': users})


@user_passes_test(is_staff_user, login_url='admin_login')
def admin_user_edit(request, pk):
    user_obj = get_object_or_404(User, pk=pk)
    form = AdminUserEditForm(request.POST or None, instance=user_obj)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, f'User "{user_obj.username}" updated.')
        return redirect('admin_users')
    return render(request, 'admin_panel/user_form.html', {'form': form, 'title': f'Edit User: {user_obj.username}'})


@user_passes_test(is_staff_user, login_url='admin_login')
def admin_user_delete(request, pk):
    user_obj = get_object_or_404(User, pk=pk)
    if user_obj == request.user:
        messages.error(request, 'You cannot delete your own account.')
        return redirect('admin_users')
    if request.method == 'POST':
        username = user_obj.username
        user_obj.delete()
        messages.success(request, f'User "{username}" deleted.')
        return redirect('admin_users')
    return render(request, 'admin_panel/confirm_delete.html', {
        'title': 'Delete User',
        'object_name': user_obj.username,
    })

