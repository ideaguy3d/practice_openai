// Very small demo dataset
const people = [
  { name: "Alice Johnson", role: "Product Manager", status: "Active" },
  { name: "Bob Smith", role: "Software Engineer", status: "Active" },
  { name: "Carol Davis", role: "Designer", status: "On leave" },
  { name: "David Lee", role: "QA Engineer", status: "Inactive" },
];

const tbody = document.getElementById("peopleTableBody");
const input = document.getElementById("nameFilter");

function renderRows(filterText = "") {
  const normalized = filterText.trim().toLowerCase();
  tbody.innerHTML = "";

  people
    .filter((person) =>
      normalized === ""
        ? true
        : person.name.toLowerCase().includes(normalized)
    )
    .forEach((person) => {
      const tr = document.createElement("tr");
      tr.innerHTML = `
        <td class="px-4 py-3 whitespace-nowrap">${person.name}</td>
        <td class="px-4 py-3 whitespace-nowrap text-gray-600">${person.role}</td>
        <td class="px-4 py-3 whitespace-nowrap">
          <span class="inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium ${
            person.status === "Active"
              ? "bg-green-100 text-green-800"
              : person.status === "On leave"
              ? "bg-yellow-100 text-yellow-800"
              : "bg-gray-100 text-gray-700"
          }">
            ${person.status}
          </span>
        </td>
      `;
      tbody.appendChild(tr);
    });
}

// Initial render
renderRows();

// Simple name filter
input.addEventListener("input", (event) => {
  renderRows(event.target.value);
});
