function add(a, b) {
  return a + b;
}

const fetchUser = async (id) => {
  const response = await fetch(`/api/users/${id}`);
  return response.json();
};

class ApiClient {
  constructor(baseUrl) {
    this.baseUrl = baseUrl;
  }

  get(path) {
    return fetch(this.baseUrl + path);
  }
}

module.exports = { add, fetchUser, ApiClient };
