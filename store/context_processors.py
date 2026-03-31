from .models import Cart, Category


def nav_categories(request):
    return {'nav_categories': Category.objects.all()[:12]}


def cart_count(request):
    if request.user.is_authenticated:
        count = sum(item.quantity for item in Cart.objects.filter(user=request.user).only('quantity'))
        return {'cart_count': count}
    return {'cart_count': 0}

