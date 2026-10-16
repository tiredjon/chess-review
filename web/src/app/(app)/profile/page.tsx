import { ProfileForm } from "@/components/auth/profile-form";

export default function ProfilePage() {
  return (
    <main className="mx-auto flex w-full max-w-2xl flex-1 flex-col gap-5 px-3 py-5 sm:px-6 sm:py-8">
      <ProfileForm />
    </main>
  );
}
