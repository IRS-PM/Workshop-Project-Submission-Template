import { Calendar, Clock, Compass, Heart, Sliders } from "@/components/icons";

export const NAV = [
  { href: "/", label: "Discover", Icon: Compass },
  { href: "/plan", label: "Meal plan", Icon: Calendar },
  { href: "/saved", label: "Saved meals", Icon: Heart },
  { href: "/history", label: "History", Icon: Clock },
  { href: "/preferences", label: "Your preferences", Icon: Sliders },
] as const;
