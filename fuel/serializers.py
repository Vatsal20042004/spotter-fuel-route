from rest_framework import serializers


class RouteRequestSerializer(serializers.Serializer):
    start = serializers.CharField(
        max_length=200, help_text='US address/place ("New York, NY") or coordinates ("40.71,-74.00").'
    )
    finish = serializers.CharField(
        max_length=200, help_text='US address/place ("Los Angeles, CA") or coordinates ("34.05,-118.24").'
    )
    geometry = serializers.ChoiceField(
        choices=["simplified", "full"],
        default="simplified",
        help_text="'simplified' (~2-mile spacing, light payload) or 'full' router geometry.",
    )

    range_miles = serializers.FloatField(
        required=False, min_value=50, max_value=2000, help_text="Vehicle range in miles (default 500)."
    )
    mpg = serializers.FloatField(
        required=False, min_value=1, max_value=100, help_text="Fuel economy in mpg (default 10)."
    )

    def validate(self, attrs):
        if attrs["start"].strip().lower() == attrs["finish"].strip().lower():
            raise serializers.ValidationError("start and finish must be different locations.")
        return attrs
