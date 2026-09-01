import { apiBlob, apiRequest } from "./client";

export type UserProfile = {
  username: string;
  role: string;
  display_name: string;
  email: string;
  phone: string;
  department: string;
  bio: string;
  avatar_url: string;
  created_at: string;
  password_updated_at: string;
  course_count?: number;
};

export type UserProfileUpdate = Pick<
  UserProfile,
  "display_name" | "email" | "phone" | "department" | "bio"
>;

export function getUserProfile() {
  return apiRequest<UserProfile>("/api/auth/me");
}

export function updateUserProfile(values: UserProfileUpdate) {
  return apiRequest<UserProfile>("/api/auth/me", {
    method: "PUT",
    body: JSON.stringify(values),
  });
}

export function changeUserPassword(currentPassword: string, newPassword: string) {
  return apiRequest<{ changed: boolean }>("/api/auth/change-password", {
    method: "POST",
    body: JSON.stringify({
      current_password: currentPassword,
      new_password: newPassword,
    }),
  });
}

export function uploadUserAvatar(file: File) {
  const body = new FormData();
  body.append("file", file);
  return apiRequest<UserProfile>("/api/auth/avatar", { method: "POST", body });
}

export function loadUserAvatar() {
  return apiBlob("/api/auth/avatar");
}
