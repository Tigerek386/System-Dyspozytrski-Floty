from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

from accounts.models import User

from .forms import DriverForm, TransportOrderForm, VehicleForm
from .models import Driver, TransportOrder, Vehicle


def _staff_only(view):
    """Redirect driver-role users to their task overview."""
    def wrapper(request, *args, **kwargs):
        if request.user.is_driver:
            return redirect("driver_dashboard")
        return view(request, *args, **kwargs)
    return wrapper


def _is_htmx(request):
    """True for htmx clicks *and* for back/forward history restores.

    Both must return the tab fragment instead of the shell: htmx swaps the
    response into #content (hx-history-elt), so the header/shell stays intact.
    Restore requests carry HX-History-Restore-Request, which happens when the
    history snapshot is not in htmx's cache (new tab, cache overflow).
    """
    return bool(
        request.headers.get("HX-Request")
        or request.headers.get("HX-History-Restore-Request")
    )


@login_required
@_staff_only
def vehicles(request):
    """Display the vehicles tab with the add-vehicle form."""
    context = {"vehicles": Vehicle.objects.all(), "vehicle_form": VehicleForm()}

    if request.method == "POST":
        form = VehicleForm(request.POST)
        if form.is_valid():
            obj = form.save()
            messages.success(request, f"Saved: {obj}")
            return redirect("vehicles")
        context["vehicle_form"] = form  # re-render with validation errors

    if _is_htmx(request):
        response = render(request, "fleet/vehicles.html", context)
        response["HX-Title"] = "Vehicles - FleetRoute"
        return response
    return render(request, "base.html", {**context, "start_url": reverse("vehicles")})


@login_required
@_staff_only
def drivers(request):
    """Display the drivers tab with add-driver and link-account forms."""
    context = {
        "drivers": Driver.objects.select_related("user").all(),
        "driver_accounts": User.objects.filter(role=User.Role.DRIVER).order_by("username"),
        "driver_form": DriverForm(),
    }

    if request.method == "POST":
        form_key = request.POST.get("form")

        if form_key == "link_driver":
            driver_id = request.POST.get("driver_id")
            user_id = request.POST.get("user_id")
            if not driver_id or not user_id:
                messages.error(request, "Select both a driver and a driver account.")
                return redirect("drivers")

            driver = get_object_or_404(Driver, pk=driver_id)
            account = get_object_or_404(User, pk=user_id, role=User.Role.DRIVER)
            existing = Driver.objects.filter(user=account).exclude(pk=driver.pk).first()
            if existing:
                messages.error(
                    request,
                    f"Account {account.username} is already linked to {existing}.",
                )
            else:
                driver.user = account
                driver.save(update_fields=["user"])
                messages.success(
                    request,
                    f"Linked account {account.username} to {driver}.",
                )
            return redirect("drivers")
        else:
            form = DriverForm(request.POST)
            if form.is_valid():
                obj = form.save()
                messages.success(request, f"Saved: {obj}")
                return redirect("drivers")
            context["driver_form"] = form

    if _is_htmx(request):
        response = render(request, "fleet/drivers.html", context)
        response["HX-Title"] = "Drivers - FleetRoute"
        return response
    return render(request, "base.html", {**context, "start_url": reverse("drivers")})


@login_required
@_staff_only
def orders(request):
    """Display the transport orders tab with status updates and the add-order form."""
    context = {
        "orders": TransportOrder.objects.select_related("vehicle", "driver").all(),
        "order_statuses": TransportOrder.Status.choices,
        "order_form": TransportOrderForm(),
    }

    if request.method == "POST":
        form_key = request.POST.get("form")

        if form_key == "status":
            order = get_object_or_404(TransportOrder, pk=request.POST.get("order_id"))
            new_status = request.POST.get("status")
            if new_status in TransportOrder.Status.values:
                order.status = new_status
                order.save(update_fields=["status"])
                messages.success(
                    request,
                    f"Order #{order.pk} status changed to {order.get_status_display()}.",
                )
            return redirect("orders")
        else:
            form = TransportOrderForm(request.POST)
            if form.is_valid():
                obj = form.save()
                messages.success(request, f"Saved: {obj}")
                return redirect("orders")
            context["order_form"] = form

    if _is_htmx(request):
        response = render(request, "fleet/orders.html", context)
        response["HX-Title"] = "Transport orders - FleetRoute"
        return response
    return render(request, "base.html", {**context, "start_url": reverse("orders")})


@login_required
def dashboard(request):
    """App shell entry point. Staff see the full dashboard; drivers get the
    shell with their task overview loaded via htmx."""
    context = {
        "vehicles": Vehicle.objects.all(),
        "drivers": Driver.objects.select_related("user").all(),
        "orders": TransportOrder.objects.select_related("vehicle", "driver").all(),
        "order_statuses": TransportOrder.Status.choices,
        "driver_accounts": User.objects.filter(role=User.Role.DRIVER).order_by("username"),
        "driver_form": DriverForm(),
        "order_form": TransportOrderForm(),
    }

    if request.method == "POST":
        form_key = request.POST.get("form")

        if form_key in ("driver", "order"):
            form_class = {
                "driver": DriverForm,
                "order": TransportOrderForm,
            }[form_key]
            form = form_class(request.POST)
            if form.is_valid():
                obj = form.save()
                messages.success(request, f"Saved: {obj}")
                return redirect("dashboard")
            context[f"{form_key}_form"] = form  # re-render with validation errors
        elif form_key == "link_driver":
            driver = get_object_or_404(Driver, pk=request.POST.get("driver_id"))
            account = get_object_or_404(
                User, pk=request.POST.get("user_id"), role=User.Role.DRIVER
            )
            if Driver.objects.filter(user=account).exclude(pk=driver.pk).exists():
                messages.error(
                    request,
                    f"Account {account.username} is already linked to "
                    f"{driver}.",
                )
            else:
                driver.user = account
                driver.save(update_fields=["user"])
                messages.success(
                    request,
                    f"Linked account {account.username} to {driver}.",
                )
            return redirect("dashboard")
        elif form_key == "status":
            order = get_object_or_404(TransportOrder, pk=request.POST.get("order_id"))
            new_status = request.POST.get("status")
            if new_status in TransportOrder.Status.values:
                order.status = new_status
                order.save(update_fields=["status"])
                messages.success(
                    request,
                    f"Order #{order.pk} status changed to {order.get_status_display()}.",
                )
            return redirect("dashboard")

    if _is_htmx(request):
        response = render(request, "fleet/dashboard.html", context)
        response["HX-Title"] = "Dashboard - FleetRoute"
        return response
    start_url = (
        reverse("driver_dashboard") if request.user.is_driver
        else reverse("dashboard")
    )
    return render(request, "base.html", {**context, "start_url": start_url})


#: statuses a driver may move their own order to from the task overview
DRIVER_ALLOWED_STATUSES = (TransportOrder.Status.IN_PROGRESS, TransportOrder.Status.COMPLETED)


@login_required
def driver_dashboard(request):
    """Task overview for logged-in drivers: only orders assigned to the
    driver profile linked to their account."""
    if not request.user.is_driver:
        return redirect("dashboard")

    profile = getattr(request.user, "driver_profile", None)
    orders = (
        TransportOrder.objects.select_related("vehicle")
        .filter(driver=profile)
    ) if profile else TransportOrder.objects.none()

    context = {
        "profile": profile,
        "active_orders": [o for o in orders if o.is_active],
        "history": [o for o in orders if not o.is_active],
        "driver_statuses": [s for s in TransportOrder.Status.choices
                            if s[0] in DRIVER_ALLOWED_STATUSES],
    }

    if request.method == "POST":
        # an unlinked driver has an empty queryset, so any order id 404s
        order = get_object_or_404(orders, pk=request.POST.get("order_id"))
        new_status = request.POST.get("status")
        if new_status in DRIVER_ALLOWED_STATUSES:
            order.status = new_status
            order.save(update_fields=["status"])
            messages.success(
                request,
                f"Order #{order.pk} status changed to {order.get_status_display()}.",
            )
        return redirect("driver_dashboard")

    if _is_htmx(request):
        response = render(request, "fleet/driver_dashboard.html", context)
        response["HX-Title"] = "My tasks - FleetRoute"
        return response
    return render(request, "base.html", {**context, "start_url": reverse("driver_dashboard")})