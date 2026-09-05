export async function api<T>(
  path: string,
  method = "GET",
  data?: unknown,
): Promise<T> {
  const response = await fetch(`/api${path}`, {
    method,
    headers:
      data instanceof FormData
        ? undefined
        : { "Content-Type": "application/json" },
    body:
      data === undefined
        ? undefined
        : data instanceof FormData
          ? data
          : JSON.stringify(data),
    cache: "no-store",
  });
  if (!response.ok) {
    const error = await response
      .json()
      .catch(() => ({ detail: "Unable to connect to the backend." }));
    throw new Error(
      typeof error.detail === "string"
        ? error.detail
        : "Check the form fields and try again.",
    );
  }
  return response.status === 204 ? (undefined as T) : response.json();
}
