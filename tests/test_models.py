from sqlalchemy.orm import configure_mappers

from data_agent.models import Base, Payment, Rating, Ride, User, Vehicle


def test_all_expected_tables_are_registered():
    assert set(Base.metadata.tables) == {
        "public.payments",
        "public.ratings",
        "public.rides",
        "public.users",
        "public.vehicles",
    }


def test_all_orm_mappers_configure_successfully():
    configure_mappers()


def test_bidirectional_relationships_are_configured():
    configure_mappers()

    assert User.vehicles.property.back_populates == "driver"
    assert Vehicle.driver.property.back_populates == "vehicles"
    assert User.rides_as_rider.property.back_populates == "rider"
    assert Ride.rider.property.back_populates == "rides_as_rider"
    assert User.rides_as_driver.property.back_populates == "driver"
    assert Ride.driver.property.back_populates == "rides_as_driver"
    assert User.payments.property.back_populates == "user"
    assert Payment.user.property.back_populates == "payments"
    assert User.ratings_given.property.back_populates == "rider"
    assert Rating.rider.property.back_populates == "ratings_given"
    assert User.ratings_received.property.back_populates == "driver"
    assert Rating.driver.property.back_populates == "ratings_received"
