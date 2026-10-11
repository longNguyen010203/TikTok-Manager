import { DashboardTopology } from "@/types/topology";

export interface IDashboardService {
  getTopology(): Promise<DashboardTopology>;
  getBaseUrl(): string;
}

export class FastApiDashboardService implements IDashboardService {
  private baseUrl: string;

  constructor(baseUrl?: string) {
    const rawUrl =
      baseUrl ||
      process.env.NEXT_PUBLIC_API_BASE_URL ||
      "http://127.0.0.1:8000";
    this.baseUrl = rawUrl.replace(/\/+$/, "");
  }

  public getBaseUrl(): string {
    return this.baseUrl;
  }

  public async getTopology(): Promise<DashboardTopology> {
    const res = await fetch(`${this.baseUrl}/dashboard/topology`, {
      method: "GET",
      headers: {
        Accept: "application/json",
      },
      cache: "no-store",
    });

    if (!res.ok) {
      let message = `Failed to fetch topology: ${res.status} ${res.statusText}`;
      try {
        const errorBody = await res.json();
        if (errorBody && errorBody.detail) {
          message = typeof errorBody.detail === "string"
            ? errorBody.detail
            : JSON.stringify(errorBody.detail);
        }
      } catch {
        // use default message
      }
      throw new Error(message);
    }

    return res.json();
  }
}

export const dashboardService: IDashboardService = new FastApiDashboardService();
